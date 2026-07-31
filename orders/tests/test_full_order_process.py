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
from orders.models import Order, OrderDelivery
from orders.services.order_delivery import (
    get_order_progress,
    mark_delivery,
    sync_order_lifecycle,
)
from orders.services.order_service import create_meal_order
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class FullOrderProcessTestCase(APITestCase):
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
            username='order_customer',
            email='order_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1711111111',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.other_user = User.objects.create_user(
            username='order_other',
            email='order_other@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.other_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=self.other_user,
            phone='1711111112',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.admin_user = User.objects.create_user(
            username='order_admin',
            email='order_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(self.admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.daily_meal = MealCategory.objects.create(
            meal_name='Daily Box',
            total_price=Decimal('180.00'),
            meal_thumbnail=make_test_image('daily-full.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        self.monthly_meal = MealCategory.objects.create(
            meal_name='Monthly Box',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('monthly-full.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )

        self.create_url = reverse('orders:order-list')
        self.admin_list_url = reverse('web_orders:admin-order-list')

        from orders.models import OrderWalletSettings

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_daily_order_one_slot_and_completes_after_delivery(self, _mock_date):
        self._auth(self.customer_token)
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.daily_meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['expected_deliveries'], 1)
        self.assertEqual(len(response.data['deliveries']), 1)
        order = Order.objects.get(public_id=response.data['public_id'])
        delivery = order.deliveries.get()

        self._auth(self.admin_token)
        mark_url = reverse(
            'web_orders:admin-order-mark-delivery',
            kwargs={'public_id': order.public_id, 'delivery_id': delivery.public_id},
        )
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 7, 10)):
            marked = self.client.post(mark_url, {'status': 'delivered'}, format='json')
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.COMPLETED)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 4, 5))
    def test_monthly_order_generates_60_slots_in_30_day_month(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        self.assertEqual(order.deliveries.count(), 60)
        progress = get_order_progress(order, reference_date=date(2026, 4, 5))
        self.assertEqual(progress['expected_deliveries'], 60)
        self.assertEqual(progress['delivered_count'], 0)
        self.assertEqual(progress['remaining_count'], 60)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_monthly_order_generates_62_slots_in_31_day_month(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.monthly_meal)
        self.assertEqual(order.deliveries.count(), 62)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.filters.timezone.localdate', return_value=date(2026, 7, 10))
    def test_admin_list_filters_and_permissions(self, _filter_date, _duration_date):
        create_meal_order(self.customer_profile, self.daily_meal)

        response = self.client.get(self.admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self._auth(self.customer_token)
        response = self.client.get(self.admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self._auth(self.admin_token)
        response = self.client.get(self.admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

        # Shared /orders/ list must also work for verified admins (not 405)
        shared_list = self.client.get(self.create_url)
        self.assertEqual(shared_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(shared_list.data), 1)

        by_type = self.client.get(self.admin_list_url, {'meal_type': 'daily'})
        self.assertEqual(by_type.status_code, status.HTTP_200_OK)
        self.assertTrue(all(row['meal_type_snapshot'] == 'daily' for row in by_type.data))

        by_month = self.client.get(self.admin_list_url, {'order_month': '2026-07'})
        self.assertEqual(by_month.status_code, status.HTTP_200_OK)
        self.assertTrue(all(row['order_month'] == '2026-07' for row in by_month.data))

        active = self.client.get(self.admin_list_url, {'activity': 'active'})
        self.assertEqual(active.status_code, status.HTTP_200_OK)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_customer_isolation_and_progress_fields(self, _mock_date):
        self._auth(self.customer_token)
        created = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.daily_meal.public_id)},
            format='json',
        )
        order_id = created.data['public_id']
        self.assertIn('expected_deliveries', created.data)
        self.assertIn('delivered_count', created.data)

        detail_url = reverse('orders:order-detail', kwargs={'public_id': order_id})
        self._auth(self.other_token)
        denied = self.client.get(detail_url)
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

        self._auth(self.customer_token)
        ok = self.client.get(detail_url)
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.data['expected_deliveries'], 1)

        current = self.client.get(reverse('orders:order-current-package'))
        self.assertEqual(current.status_code, status.HTTP_200_OK)
        self.assertEqual(current.data['current_package']['remaining_count'], 1)

        # Customer cannot mark delivery via admin endpoint
        delivery_id = ok.data['deliveries'][0]['public_id']
        mark_url = reverse(
            'web_orders:admin-order-mark-delivery',
            kwargs={'public_id': order_id, 'delivery_id': delivery_id},
        )
        forbidden = self.client.post(mark_url, {'status': 'delivered'}, format='json')
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_duplicate_mark_and_invalid_transition(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()

        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 7, 10)):
            first = mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
            second = mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(first.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(second.status, OrderDelivery.DeliveryStatus.DELIVERED)

        from orders.services.order_delivery import DeliveryError

        with self.assertRaises(DeliveryError):
            mark_delivery(delivery, 'skipped', marked_by=self.admin_user)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 1))
    def test_sync_lifecycle_activates_due_orders(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        self.assertEqual(order.order_status, Order.OrderStatus.CONFIRMED)
        result = sync_order_lifecycle(reference_date=date(2026, 7, 1))
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.ACTIVE)
        self.assertGreaterEqual(result['activated'], 1)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    def test_today_board_lists_scheduled_deliveries(self, _mock_date):
        create_meal_order(self.customer_profile, self.daily_meal)
        self._auth(self.admin_token)
        with patch('orders.api.views.timezone.localdate', return_value=date(2026, 7, 10)):
            web_url = reverse('web_orders:admin-order-today-board')
            web_response = self.client.get(web_url, {'service_date': '2026-07-10'})
            shared_url = reverse('orders:order-today-board')
            shared_response = self.client.get(shared_url, {'service_date': '2026-07-10'})
        self.assertEqual(web_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(web_response.data), 1)
        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(shared_response.data), 1)
