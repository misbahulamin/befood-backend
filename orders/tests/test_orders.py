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
from orders.models import Order
from orders.services.order_duration import calculate_order_period
from orders.services.order_service import create_meal_order
from orders.services.subscription_service import subscribe_customer
from user_management.models import CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OrderAPITestCase(APITestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.customer_user = User.objects.create_user(
            username='customer1',
            email='customer1@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345678',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.unverified_user = User.objects.create_user(
            username='unverified',
            email='unverified@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.unverified_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=self.unverified_user,
            phone='1712345679',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=False,
        )
        self.unverified_token = Token.objects.create(user=self.unverified_user)

        self.other_user = User.objects.create_user(
            username='customer2',
            email='customer2@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.other_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=self.other_user,
            phone='1712345680',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.active_meal = MealCategory.objects.create(
            meal_name='Monthly Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('monthly.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.inactive_meal = MealCategory.objects.create(
            meal_name='Inactive Package',
            total_price=Decimal('500.00'),
            meal_thumbnail=make_test_image('inactive.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=False,
        )

        self.create_url = reverse('orders:order-list')
        self.my_orders_url = reverse('orders:order-my-orders')
        self.current_package_url = reverse('orders:order-current-package')

        # Existing order flows are not about wallet eligibility; disable the floor.
        from orders.models import OrderWalletSettings

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()

    def _auth(self, token=None):
        token = token or self.customer_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def _create_order_payload(self, meal_public_id=None, note=''):
        return {
            'meal_public_id': str(meal_public_id or self.active_meal.public_id),
            'customer_note': note,
        }

    def test_verified_customer_order_create_is_retired(self):
        self._auth()
        response = self.client.post(self.create_url, self._create_order_payload(note='After 1 PM'), format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error_code'], 'SUBSCRIBE_REQUIRED')
        self.assertEqual(Order.objects.count(), 0)

    def test_unauthenticated_user_cannot_create_order(self):
        response = self.client.post(self.create_url, self._create_order_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_user_cannot_create_order(self):
        self._auth(self.unverified_token)
        response = self.client.post(self.create_url, self._create_order_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_my_orders_returns_only_own_orders(self, _mock_date):
        create_meal_order(self.customer_profile, self.active_meal)

        self._auth(self.other_token)
        response = self.client.get(self.my_orders_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        self._auth()
        response = self.client.get(self.my_orders_url)
        self.assertEqual(len(response.data), 1)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_order_detail_cannot_be_accessed_by_another_customer(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.active_meal)

        self._auth(self.other_token)
        detail_url = reverse('orders:order-detail', kwargs={'public_id': order.public_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.api.views.timezone.localdate', return_value=date(2026, 7, 10))
    def test_cancel_order_changes_status_to_cancelled(self, _mock_view_date, _mock_duration_date):
        daily_meal = MealCategory.objects.create(
            meal_name='Daily Package',
            total_price=Decimal('180.00'),
            meal_thumbnail=make_test_image('daily-cancel.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            is_active=True,
        )
        order = create_meal_order(self.customer_profile, daily_meal)
        self._auth()
        cancel_url = reverse('orders:order-cancel', kwargs={'public_id': order.public_id})
        response = self.client.post(cancel_url, {'note': 'Changed mind'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_status'], 'cancelled')
        order.refresh_from_db()
        self.assertEqual(order.status_history.count(), 1)

    @patch('orders.services.subscription_service.business_today', return_value=date(2026, 7, 10))
    @patch('orders.services.subscription_service.published_schedule_for_meal', return_value=object())
    def test_current_package_endpoint_returns_active_subscription(self, _pub, _today):
        self.active_meal.is_subscribable = True
        self.active_meal.save(update_fields=['is_subscribable'])
        subscription = subscribe_customer(self.customer_profile, self.active_meal, today=date(2026, 7, 10))
        self._auth()
        response = self.client.get(self.current_package_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['current_package'])
        self.assertEqual(
            response.data['current_package']['public_id'],
            str(subscription.public_id),
        )
        self.assertEqual(
            response.data['current_subscription']['public_id'],
            str(subscription.public_id),
        )

    def test_current_package_returns_null_when_no_subscription(self):
        self._auth()
        response = self.client.get(self.current_package_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['current_package'])
        self.assertIn('No active meal subscription', response.data['message'])


class OrderDurationTestCase(APITestCase):
    def test_daily_duration_is_one_day(self):
        period = calculate_order_period(MealCategory.MealType.DAILY, reference_date=date(2026, 7, 10))
        self.assertEqual(period.start_date, date(2026, 7, 10))
        self.assertEqual(period.end_date, date(2026, 7, 10))
        self.assertEqual(period.service_days_count, 1)
        self.assertEqual(period.order_month, '2026-07')

    def test_weekly_duration_is_seven_days(self):
        period = calculate_order_period(MealCategory.MealType.WEEKLY, reference_date=date(2026, 7, 10))
        self.assertEqual(period.start_date, date(2026, 7, 10))
        self.assertEqual(period.end_date, date(2026, 7, 16))
        self.assertEqual(period.service_days_count, 7)

    def test_half_monthly_duration_is_fifteen_days(self):
        period = calculate_order_period(MealCategory.MealType.HALF_MONTHLY, reference_date=date(2026, 7, 10))
        self.assertEqual(period.start_date, date(2026, 7, 10))
        self.assertEqual(period.end_date, date(2026, 7, 24))
        self.assertEqual(period.service_days_count, 15)

    def test_monthly_duration_uses_current_calendar_month_days(self):
        july_period = calculate_order_period(MealCategory.MealType.MONTHLY, reference_date=date(2026, 7, 10))
        self.assertEqual(july_period.start_date, date(2026, 7, 1))
        self.assertEqual(july_period.end_date, date(2026, 7, 31))
        self.assertEqual(july_period.service_days_count, 31)

        feb_period = calculate_order_period(MealCategory.MealType.MONTHLY, reference_date=date(2028, 2, 15))
        self.assertEqual(feb_period.start_date, date(2028, 2, 1))
        self.assertEqual(feb_period.end_date, date(2028, 2, 29))
        self.assertEqual(feb_period.service_days_count, 29)

    def test_six_months_duration_calculated_correctly(self):
        period = calculate_order_period(MealCategory.MealType.SIX_MONTHS, reference_date=date(2026, 1, 31))
        self.assertEqual(period.start_date, date(2026, 1, 31))
        self.assertEqual(period.end_date, date(2026, 7, 30))
        self.assertEqual(period.service_days_count, 181)

    def test_yearly_duration_calculated_correctly(self):
        period = calculate_order_period(MealCategory.MealType.YEARLY, reference_date=date(2024, 2, 29))
        self.assertEqual(period.start_date, date(2024, 2, 29))
        self.assertEqual(period.end_date, date(2025, 2, 27))
        self.assertEqual(period.service_days_count, 365)
