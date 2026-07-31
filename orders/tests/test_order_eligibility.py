from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import Order, OrderWalletSettings
from orders.services.order_service import (
    FrozenWalletOrderError,
    InsufficientWalletBalanceError,
    MonthLockError,
    check_existing_monthly_lock,
    create_meal_order,
)
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import Wallet, WalletTransaction
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _set_wallet_min(amount: Decimal) -> OrderWalletSettings:
    settings_obj = OrderWalletSettings.load()
    settings_obj.min_wallet_balance_to_order = amount
    settings_obj.save()
    return settings_obj


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MonthLockServiceTests(TestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='lock_customer',
            email='lock_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.user.groups.add(group)
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712000001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        _set_wallet_min(Decimal('0.00'))
        self.monthly = MealCategory.objects.create(
            meal_name='Monthly Lock',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('monthly-lock.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.weekly = MealCategory.objects.create(
            meal_name='Weekly Lock',
            total_price=Decimal('700.00'),
            meal_thumbnail=make_test_image('weekly-lock.jpg'),
            meal_type=MealCategory.MealType.WEEKLY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_service_raises_month_lock(self, _mock_date):
        create_meal_order(self.profile, self.monthly)
        with self.assertRaises(MonthLockError):
            create_meal_order(self.profile, self.weekly)
        self.assertEqual(Order.objects.filter(customer=self.profile).count(), 1)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_cancelled_does_not_lock(self, _mock_date):
        order = create_meal_order(self.profile, self.monthly)
        order.order_status = Order.OrderStatus.CANCELLED
        order.save(update_fields=['order_status'])
        check_existing_monthly_lock(self.profile, '2026-07')
        second = create_meal_order(self.profile, self.weekly)
        self.assertEqual(second.order_month, '2026-07')

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_different_month_allowed(self, _mock_date):
        Order.objects.create(
            customer=self.profile,
            meal=self.monthly,
            meal_name_snapshot=self.monthly.meal_name,
            meal_type_snapshot=self.monthly.meal_type,
            meal_period_snapshot=self.monthly.meal_period,
            total_price_snapshot=self.monthly.total_price,
            per_meal_price_snapshot=Decimal('50.00'),
            order_status=Order.OrderStatus.ACTIVE,
            order_start_date=date(2026, 7, 1),
            order_end_date=date(2026, 7, 31),
            service_days_count=31,
            order_month='2026-07',
        )
        august = create_meal_order(self.profile, self.monthly)
        self.assertEqual(august.order_month, '2026-08')


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OrderWalletEligibilityTests(APITestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.customer_user = User.objects.create_user(
            username='wallet_order_customer',
            email='wallet_order_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712000002',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.admin_user = User.objects.create_user(
            username='wallet_order_admin',
            email='wallet_order_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(self.admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.meal = MealCategory.objects.create(
            meal_name='Eligibility Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('elig.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        _set_wallet_min(Decimal('500.00'))
        self.create_url = reverse('orders:order-list')
        self.settings_url = reverse('web_orders:order-wallet-settings')

    def _auth(self, token=None):
        token = token or self.customer_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def _fund(self, amount: Decimal):
        wallet = get_or_create_wallet(self.customer_profile)
        if amount > 0:
            credit_wallet(wallet, amount)
        return wallet

    def test_admin_settings_defaults(self):
        OrderWalletSettings.objects.all().delete()
        self._auth(self.admin_token)
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['min_wallet_balance_to_order'], '500.00')

    def test_admin_can_patch_minimum(self):
        self._auth(self.admin_token)
        patched = self.client.patch(
            self.settings_url,
            {'min_wallet_balance_to_order': '600.00'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['min_wallet_balance_to_order'], '600.00')

        lowered = self.client.patch(
            self.settings_url,
            {'min_wallet_balance_to_order': '300.00'},
            format='json',
        )
        self.assertEqual(lowered.status_code, status.HTTP_200_OK)
        self.assertEqual(lowered.data['min_wallet_balance_to_order'], '300.00')

    def test_admin_rejects_negative_minimum(self):
        self._auth(self.admin_token)
        before = OrderWalletSettings.load().min_wallet_balance_to_order
        response = self.client.patch(
            self.settings_url,
            {'min_wallet_balance_to_order': '-1.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrderWalletSettings.load().min_wallet_balance_to_order, before)

    def test_admin_rejects_too_many_decimals(self):
        self._auth(self.admin_token)
        response = self.client.patch(
            self.settings_url,
            {'min_wallet_balance_to_order': '500.123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_update_settings(self):
        self._auth(self.customer_token)
        response = self.client.patch(
            self.settings_url,
            {'min_wallet_balance_to_order': '100.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_settings_rejected(self):
        self.client.credentials()
        response = self.client.get(self.settings_url)
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_balance_at_minimum_allows_order_without_debit(self, _mock_date):
        wallet = self._fund(Decimal('500.00'))
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('500.00'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=wallet,
                type=WalletTransaction.Type.PAYMENT,
            ).count(),
            0,
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_balance_below_minimum_rejected(self, _mock_date):
        self._fund(Decimal('499.99'))
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient wallet balance', str(response.data))
        self.assertEqual(Order.objects.filter(customer=self.customer_profile).count(), 0)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_missing_wallet_treated_as_zero(self, _mock_date):
        self.assertFalse(Wallet.objects.filter(customer=self.customer_profile).exists())
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient wallet balance', str(response.data))

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_frozen_wallet_rejected(self, _mock_date):
        wallet = self._fund(Decimal('1000.00'))
        wallet.status = Wallet.Status.FROZEN
        wallet.save(update_fields=['status'])
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('frozen', str(response.data).lower())
        self.assertEqual(Order.objects.filter(customer=self.customer_profile).count(), 0)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_month_lock_wins_over_low_balance(self, _mock_date):
        _set_wallet_min(Decimal('0.00'))
        create_meal_order(self.customer_profile, self.meal)
        _set_wallet_min(Decimal('500.00'))
        # No wallet / low balance, but month lock should surface first
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already have a meal package for this month', str(response.data))

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_admin_lowered_minimum_allows_order(self, _mock_date):
        _set_wallet_min(Decimal('300.00'))
        self._fund(Decimal('300.00'))
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_service_insufficient_and_frozen_errors(self, _mock_date):
        _set_wallet_min(Decimal('500.00'))
        with self.assertRaises(InsufficientWalletBalanceError):
            create_meal_order(self.customer_profile, self.meal)

        wallet = self._fund(Decimal('1000.00'))
        wallet.status = Wallet.Status.FROZEN
        wallet.save(update_fields=['status'])
        with self.assertRaises(FrozenWalletOrderError):
            create_meal_order(self.customer_profile, self.meal)
