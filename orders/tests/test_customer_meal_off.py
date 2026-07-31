from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import MealOffSettings, Order, OrderDelivery
from orders.services.meal_off import (
    MealOffError,
    can_meal_off,
    customer_meal_off,
    meal_off_deadline,
)
from orders.services.order_service import create_meal_order
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class MealOffDeadlineHelperTests(SimpleTestCase):
    def setUp(self):
        self.settings_obj = MealOffSettings(
            timezone='Asia/Dhaka',
            lunch_off_time=time(23, 59),
            dinner_off_time=time(14, 0),
        )

    def test_lunch_deadline_is_previous_day_2359(self):
        deadline = meal_off_deadline(date(2026, 7, 24), 'lunch', self.settings_obj)
        self.assertEqual(deadline.date(), date(2026, 7, 23))
        self.assertEqual(deadline.time(), time(23, 59))
        self.assertEqual(str(deadline.tzinfo), 'Asia/Dhaka')

    def test_dinner_deadline_is_same_day_1400(self):
        deadline = meal_off_deadline(date(2026, 7, 23), 'dinner', self.settings_obj)
        self.assertEqual(deadline.date(), date(2026, 7, 23))
        self.assertEqual(deadline.time(), time(14, 0))

    def test_can_meal_off_inclusive_at_deadline(self):
        delivery = OrderDelivery(
            service_date=date(2026, 7, 24),
            meal_period='lunch',
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        delivery.order = Order(order_status=Order.OrderStatus.ACTIVE)
        tz = ZoneInfo('Asia/Dhaka')
        at_deadline = datetime(2026, 7, 23, 23, 59, 0, tzinfo=tz)
        just_after = datetime(2026, 7, 23, 23, 59, 1, tzinfo=tz)
        self.assertTrue(can_meal_off(delivery, now=at_deadline, settings_obj=self.settings_obj))
        self.assertFalse(can_meal_off(delivery, now=just_after, settings_obj=self.settings_obj))

    def test_dinner_just_after_1400_rejected(self):
        delivery = OrderDelivery(
            service_date=date(2026, 7, 23),
            meal_period='dinner',
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        delivery.order = Order(order_status=Order.OrderStatus.ACTIVE)
        tz = ZoneInfo('Asia/Dhaka')
        before = datetime(2026, 7, 23, 13, 59, 0, tzinfo=tz)
        after = datetime(2026, 7, 23, 14, 0, 1, tzinfo=tz)
        self.assertTrue(can_meal_off(delivery, now=before, settings_obj=self.settings_obj))
        self.assertFalse(can_meal_off(delivery, now=after, settings_obj=self.settings_obj))


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CustomerMealOffAPITestCase(APITestCase):
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
            username='mealoff_customer',
            email='mealoff_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1711222333',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.other_user = User.objects.create_user(
            username='mealoff_other',
            email='mealoff_other@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.other_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=self.other_user,
            phone='1711222334',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.admin_user = User.objects.create_user(
            username='mealoff_admin',
            email='mealoff_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(self.admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.monthly_meal = MealCategory.objects.create(
            meal_name='Monthly Both',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('monthly-mealoff.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.daily_lunch = MealCategory.objects.create(
            meal_name='Daily Lunch',
            total_price=Decimal('180.00'),
            meal_thumbnail=make_test_image('daily-lunch-mealoff.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        MealOffSettings.load()

        from orders.models import OrderWalletSettings

        wallet_settings = OrderWalletSettings.load()
        wallet_settings.min_wallet_balance_to_order = Decimal('0.00')
        wallet_settings.save()

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_meal_off_lunch_before_deadline(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 7, 10, 20, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        lunch = order.deliveries.get(service_date=date(2026, 7, 11), meal_period='lunch')
        self._auth(self.customer_token)
        url = reverse(
            'orders:order-meal-off',
            kwargs={'public_id': order.public_id, 'delivery_id': lunch.public_id},
        )
        # Prefer noslash name if router name differs
        if 'meal-off' not in url:
            url = f'/orders/{order.public_id}/deliveries/{lunch.public_id}/meal-off'
        response = self.client.post(url, {'note': 'Travel'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'skipped')
        self.assertEqual(response.data['skip_source'], 'customer')
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_meal_off_dinner_before_deadline(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 7, 10, 13, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        dinner = order.deliveries.get(service_date=date(2026, 7, 10), meal_period='dinner')
        updated = customer_meal_off(dinner, self.customer_user, note='Busy')
        self.assertEqual(updated.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(updated.skip_source, OrderDelivery.SkipSource.CUSTOMER)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_meal_off_after_lunch_deadline_rejected(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 7, 11, 0, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        lunch = order.deliveries.get(service_date=date(2026, 7, 11), meal_period='lunch')
        with self.assertRaises(MealOffError):
            customer_meal_off(lunch, self.customer_user)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_other_user_cannot_meal_off(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 7, 10, 20, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        lunch = order.deliveries.get(service_date=date(2026, 7, 11), meal_period='lunch')
        self._auth(self.other_token)
        response = self.client.post(
            f'/orders/{order.public_id}/deliveries/{lunch.public_id}/meal-off',
            {},
            format='json',
        )
        self.assertIn(response.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_daily_completes_after_meal_off(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 7, 9, 20, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.daily_lunch)
        delivery = order.deliveries.get()
        customer_meal_off(delivery, self.customer_user)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.COMPLETED)

    def test_settings_defaults_and_admin_update(self):
        self._auth(self.admin_token)
        url = reverse('web_orders:meal-off-settings')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['timezone'], 'Asia/Dhaka')
        self.assertEqual(response.data['lunch_off_time'], '23:59:00')
        self.assertEqual(response.data['dinner_off_time'], '14:00:00')

        patched = self.client.patch(url, {'dinner_off_time': '15:00:00'}, format='json')
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['dinner_off_time'], '15:00:00')

        bad = self.client.patch(url, {'timezone': 'Not/AZone'}, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_update_settings(self):
        self._auth(self.customer_token)
        response = self.client.patch(
            reverse('web_orders:meal-off-settings'),
            {'dinner_off_time': '16:00:00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_detail_exposes_can_meal_off(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 7, 10, 20, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        self._auth(self.customer_token)
        detail = self.client.get(reverse('orders:order-detail', kwargs={'public_id': order.public_id}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        lunch = next(
            d for d in detail.data['deliveries']
            if d['service_date'] == '2026-07-11' and d['meal_period'] == 'lunch'
        )
        self.assertTrue(lunch['can_meal_off'])
        self.assertIn('2026-07-10', lunch['meal_off_deadline_at'])
