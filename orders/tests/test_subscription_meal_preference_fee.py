"""Subscription meal preference + delivery fee calculation tests."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import CustomerSubscription, OrderDelivery, OrderWalletSettings
from orders.services.subscription_service import (
    ensure_subscription_deliveries,
    subscribe_customer,
)
from user_management.models import CustomerProfile
from wallet.models import WalletTransaction
from wallet.services.ledger import credit_wallet, get_or_create_wallet
from wallet.services.subscription_delivery_fee import (
    SubscriptionDeliveryFeeError,
    calculate_subscription_delivery_fee,
    format_fee_summary,
    normalize_quantity,
)


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _set_wallet_min(amount: Decimal) -> None:
    settings_obj = OrderWalletSettings.load()
    settings_obj.min_wallet_balance_to_order = amount
    settings_obj.save()


class SubscriptionDeliveryFeeUnitTest(APITestCase):
    def test_lunch_and_dinner_fee(self):
        lunch = calculate_subscription_delivery_fee('lunch', 1)
        dinner = calculate_subscription_delivery_fee('dinner', 9)
        self.assertEqual(lunch['amount'], Decimal('200.00'))
        self.assertEqual(dinner['amount'], Decimal('200.00'))
        self.assertEqual(lunch['fee_rule_code'], 'single_period')

    def test_both_tiers_and_boundaries(self):
        self.assertEqual(
            calculate_subscription_delivery_fee('both', 1)['amount'],
            Decimal('400.00'),
        )
        self.assertEqual(
            calculate_subscription_delivery_fee('both', 3)['amount'],
            Decimal('400.00'),
        )
        self.assertEqual(
            calculate_subscription_delivery_fee('both', 4)['amount'],
            Decimal('350.00'),
        )
        self.assertEqual(
            calculate_subscription_delivery_fee('both', 5)['amount'],
            Decimal('350.00'),
        )
        self.assertEqual(
            calculate_subscription_delivery_fee('both', 6)['amount'],
            Decimal('300.00'),
        )

    def test_invalid_quantity(self):
        with self.assertRaises(SubscriptionDeliveryFeeError):
            normalize_quantity(0)
        with self.assertRaises(SubscriptionDeliveryFeeError):
            normalize_quantity('x')

    def test_format_fee_summary(self):
        summary = format_fee_summary(calculate_subscription_delivery_fee('both', 2))
        self.assertEqual(summary['monthly_delivery_fee'], '400.00')
        self.assertEqual(summary['fee_rule_code'], 'both_q_1_3')
        self.assertEqual(summary['quantity'], 2)


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SubscriptionMealPreferenceAPITestCase(APITestCase):
    def setUp(self):
        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=date(2026, 7, 10),
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='pref_customer',
            email='pref_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.user.groups.add(customer_group)
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712555991',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.both_plan = MealCategory.objects.create(
            meal_name='Both Plan',
            meal_thumbnail=make_test_image('both.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('3000.00'),
            is_active=True,
            is_subscribable=True,
        )
        self.lunch_plan = MealCategory.objects.create(
            meal_name='Lunch Plan',
            meal_thumbnail=make_test_image('lunch.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            total_price=Decimal('2000.00'),
            is_active=True,
            is_subscribable=True,
        )
        _set_wallet_min(Decimal('0'))
        wallet = get_or_create_wallet(self.profile)
        credit_wallet(wallet, Decimal('500.00'), note='test fund')

        self.subscriptions_url = reverse('subscriptions:subscription-list')
        self.quote_url = reverse('subscriptions:subscription-quote')

    def _periods(self, subscription):
        return set(
            subscription.deliveries.values_list('meal_period', flat=True).distinct()
        )

    def test_subscribe_lunch_only_creates_lunch_slots(self):
        response = self.client.post(
            self.subscriptions_url,
            {
                'plan_public_id': str(self.both_plan.public_id),
                'meal_preference': 'lunch',
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meal_period_snapshot'], 'lunch')
        self.assertEqual(response.data['quantity'], 1)
        self.assertEqual(response.data['monthly_delivery_fee'], '200.00')
        sub = CustomerSubscription.objects.get(public_id=response.data['public_id'])
        self.assertEqual(self._periods(sub), {'lunch'})
        self.assertFalse(
            sub.deliveries.filter(meal_period=OrderDelivery.MealPeriod.DINNER).exists()
        )

    def test_subscribe_dinner_only_creates_dinner_slots(self):
        response = self.client.post(
            self.subscriptions_url,
            {
                'plan_public_id': str(self.both_plan.public_id),
                'meal_preference': 'dinner',
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meal_period_snapshot'], 'dinner')
        sub = CustomerSubscription.objects.get(public_id=response.data['public_id'])
        self.assertEqual(self._periods(sub), {'dinner'})

    def test_subscribe_both_creates_both_periods(self):
        response = self.client.post(
            self.subscriptions_url,
            {
                'plan_public_id': str(self.both_plan.public_id),
                'meal_preference': 'both',
                'quantity': 2,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meal_period_snapshot'], 'both')
        self.assertEqual(response.data['quantity'], 2)
        self.assertEqual(response.data['monthly_delivery_fee'], '400.00')
        sub = CustomerSubscription.objects.get(public_id=response.data['public_id'])
        self.assertEqual(self._periods(sub), {'lunch', 'dinner'})

    def test_legacy_omit_preference_uses_package_period(self):
        response = self.client.post(
            self.subscriptions_url,
            {'plan_public_id': str(self.both_plan.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meal_period_snapshot'], 'both')
        self.assertEqual(response.data['quantity'], 1)
        sub = CustomerSubscription.objects.get(public_id=response.data['public_id'])
        self.assertEqual(self._periods(sub), {'lunch', 'dinner'})

    def test_preference_outside_package_rejected(self):
        response = self.client.post(
            self.subscriptions_url,
            {
                'plan_public_id': str(self.lunch_plan.public_id),
                'meal_preference': 'dinner',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CustomerSubscription.objects.filter(customer=self.profile).exists())

    def test_ensure_respects_existing_lunch_only(self):
        sub = subscribe_customer(
            self.profile,
            self.both_plan,
            meal_preference='lunch',
            quantity=1,
            today=date(2026, 7, 10),
        )
        ensure_subscription_deliveries(sub, today=date(2026, 7, 15))
        self.assertEqual(self._periods(sub), {'lunch'})

    def test_quote_both_fee_no_side_effects(self):
        before_subs = CustomerSubscription.objects.count()
        before_txns = WalletTransaction.objects.count()
        response = self.client.post(
            self.quote_url,
            {
                'plan_public_id': str(self.both_plan.public_id),
                'meal_preference': 'both',
                'quantity': 4,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['monthly_delivery_fee'], '350.00')
        self.assertEqual(response.data['quantity'], 4)
        self.assertEqual(response.data['meal_preference'], 'both')
        self.assertEqual(CustomerSubscription.objects.count(), before_subs)
        self.assertEqual(WalletTransaction.objects.count(), before_txns)

    def test_quote_invalid_preference(self):
        response = self.client.post(
            self.quote_url,
            {
                'plan_public_id': str(self.lunch_plan.public_id),
                'meal_preference': 'both',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_subscribe_does_not_create_delivery_fee_payment(self):
        response = self.client.post(
            self.subscriptions_url,
            {
                'plan_public_id': str(self.both_plan.public_id),
                'meal_preference': 'lunch',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.DELIVERY_FEE_PAYMENT
            ).exists()
        )
