from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from delivery_zones.services.assignment import assign_customer_location
from delivery_zones.services.locations import create_location
from delivery_zones.services.zones import assign_delivery_man, create_zone
from meals.models import MealCategory
from orders.models import (
    CustomerSubscription,
    DeliveryActivityLog,
    DeliveryManDailySummary,
    OrderDelivery,
)
from orders.services.delivery_logistics import LogisticsError, transition_logistics_status
from user_management.models import AdminProfile, CustomerProfile, RiderProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class AdminDeliveryman360Tests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='DELIVERY_MAN')
        Group.objects.get_or_create(name='ADMIN')
        Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='admin360',
            email='admin360@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(Group.objects.get(name='ADMIN'))
        self.admin_client = APIClient()
        self.admin_client.credentials(
            HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.admin_user).key}'
        )

        rider_user = User.objects.create_user(
            username='rider360',
            email='rider360@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            last_name='Khan',
            is_active=True,
        )
        rider_user.groups.add(Group.objects.get(name='DELIVERY_MAN'))
        self.rider = RiderProfile.objects.create(
            user=rider_user,
            phone='1714000001',
            approval_status=RiderProfile.ApprovalStatus.APPROVED,
            is_verified=True,
            is_email_verified=True,
            verified_at=timezone.now(),
            is_available=True,
        )
        self.rider_client = APIClient()
        self.rider_client.credentials(
            HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=rider_user).key}'
        )

        cust_user = User.objects.create_user(
            username='cust360',
            email='cust360@example.com',
            password='StrongPassword123',
            first_name='Hasan',
            is_active=True,
        )
        self.customer = CustomerProfile.objects.create(
            user=cust_user,
            phone='1714000099',
            is_email_verified=True,
        )

        self.zone = create_zone(name='Zone 02', code='zone-02', priority=1)
        self.location = create_location(
            name='Zamal Khan', zone_public_id=self.zone.public_id, priority=1
        )
        assign_delivery_man(self.zone, delivery_man_public_id=self.rider.public_id)
        assign_customer_location(self.customer, location_public_id=self.location.public_id)

        self.service_date = date(2026, 9, 20)
        self.plan = MealCategory.objects.create(
            meal_name='Student Package 360',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('plan360.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        self.subscription = CustomerSubscription.objects.create(
            customer=self.customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=self.service_date,
        )

    def _seed_delivery(self, meal_period='lunch'):
        return OrderDelivery.objects.create(
            subscription=self.subscription,
            service_date=self.service_date,
            meal_period=meal_period,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
            delivery_label_snapshot='Home',
            delivery_full_address_snapshot='House 1',
            delivery_area_snapshot=self.location.name,
            delivery_city_snapshot='Chattogram',
        )

    def test_list_and_overview_require_admin(self):
        anon = APIClient()
        self.assertEqual(
            anon.get('/api/v1/web/delivery-men/').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.rider_client.get('/api/v1/web/delivery-men/').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_list_overview_and_unknown_404(self):
        resp = self.admin_client.get('/api/v1/web/delivery-men/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(any(r['public_id'] == str(self.rider.public_id) for r in resp.data['results']))
        row = next(r for r in resp.data['results'] if r['public_id'] == str(self.rider.public_id))
        self.assertIn('today_delivery', row)
        self.assertIn('monthly_delivery', row)
        self.assertIn('lifetime_delivery', row)
        self.assertEqual(row['assigned_zone']['code'], 'zone-02')

        overview = self.admin_client.get(f'/api/v1/web/delivery-men/{self.rider.public_id}/')
        self.assertEqual(overview.status_code, status.HTTP_200_OK)
        self.assertIn('today', overview.data)
        self.assertIn('month', overview.data)
        self.assertIn('lifetime', overview.data)
        self.assertNotIn('deliveries', overview.data)
        self.assertNotIn('timeline', overview.data)

        missing = self.admin_client.get(
            '/api/v1/web/delivery-men/00000000-0000-0000-0000-000000000099/'
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_writes_attribution_activity_summary_and_gps(self):
        delivery = self._seed_delivery('dinner')
        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ), patch(
            'notifications.services.meal_delivery_notifications.notify_meal_delivered',
            return_value=None,
        ):
            resp = self.rider_client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {
                    'status': 'delivered',
                    'latitude': '22.356900',
                    'longitude': '91.783200',
                },
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(delivery.delivered_by_rider_id, self.rider.pk)
        self.assertEqual(delivery.logistics_status, OrderDelivery.LogisticsStatus.DELIVERED)
        self.assertIsNotNone(delivery.delivered_at)
        self.assertEqual(delivery.completion_latitude, Decimal('22.356900'))
        self.assertTrue(
            DeliveryActivityLog.objects.filter(
                delivery=delivery, status='delivered', rider=self.rider
            ).exists()
        )
        summary = DeliveryManDailySummary.objects.get(rider=self.rider, date=self.service_date)
        self.assertEqual(summary.dinner_count, 1)
        self.assertEqual(summary.completed_count, 1)

    def test_legacy_mark_payload_still_works(self):
        delivery = self._seed_delivery('lunch')
        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ), patch(
            'notifications.services.meal_delivery_notifications.notify_meal_delivered',
            return_value=None,
        ):
            resp = self.rider_client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        delivery.refresh_from_db()
        self.assertIsNone(delivery.completion_latitude)

    def test_skip_does_not_increment_completed_kpi(self):
        delivery = self._seed_delivery('lunch')
        from orders.services.order_delivery import mark_delivery

        mark_delivery(
            delivery,
            OrderDelivery.DeliveryStatus.SKIPPED,
            marked_by=self.admin_user,
            note='admin skip',
            logistics_source='admin',
        )
        self.assertFalse(
            DeliveryManDailySummary.objects.filter(rider=self.rider, date=self.service_date).exists()
        )

    def test_deliveries_filters_and_unknown_param(self):
        delivery = self._seed_delivery('lunch')
        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ), patch(
            'notifications.services.meal_delivery_notifications.notify_meal_delivered',
            return_value=None,
        ):
            self.rider_client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )

        bad = self.admin_client.get(
            f'/api/v1/web/delivery-men/{self.rider.public_id}/deliveries/',
            {'foo': 'bar'},
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        ok = self.admin_client.get(
            f'/api/v1/web/delivery-men/{self.rider.public_id}/deliveries/',
            {'meal_period': 'lunch', 'date_from': '2026-09-01', 'date_to': '2026-09-30'},
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(len(ok.data['results']), 1)

    def test_timeline_route_rankings(self):
        delivery = self._seed_delivery('dinner')
        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ), patch(
            'notifications.services.meal_delivery_notifications.notify_meal_delivered',
            return_value=None,
        ):
            self.rider_client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )

        timeline = self.admin_client.get(
            f'/api/v1/web/delivery-men/{self.rider.public_id}/timeline/',
            {'date': timezone.localdate().isoformat()},
        )
        self.assertEqual(timeline.status_code, status.HTTP_200_OK)
        events = timeline.data['results'] if 'results' in timeline.data else timeline.data
        self.assertTrue(any(e['status'] == 'delivered' for e in events))

        missing_route = self.admin_client.get(
            f'/api/v1/web/delivery-men/{self.rider.public_id}/route/'
        )
        self.assertEqual(missing_route.status_code, status.HTTP_400_BAD_REQUEST)

        route = self.admin_client.get(
            f'/api/v1/web/delivery-men/{self.rider.public_id}/route/',
            {'service_date': self.service_date.isoformat(), 'meal_period': 'dinner'},
        )
        self.assertEqual(route.status_code, status.HTTP_200_OK)
        self.assertEqual(route.data['starting_point']['label'], 'Hub')
        self.assertGreaterEqual(len(route.data['stops']), 1)

        rankings = self.admin_client.get(
            '/api/v1/web/delivery-men/rankings/',
            {'date_from': '2026-09-01', 'date_to': '2026-09-30'},
        )
        self.assertEqual(rankings.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(r['public_id'] == str(self.rider.public_id) for r in rankings.data['results'])
        )

    def test_logistics_illegal_transition_rejected(self):
        delivery = self._seed_delivery('lunch')
        transition_logistics_status(
            delivery,
            OrderDelivery.LogisticsStatus.PICKED_UP,
            rider=self.rider,
            source='deliveryman',
        )
        delivery.refresh_from_db()
        with self.assertRaises(LogisticsError) as ctx:
            transition_logistics_status(
                delivery,
                OrderDelivery.LogisticsStatus.ASSIGNED,
                rider=self.rider,
                source='deliveryman',
            )
        self.assertEqual(ctx.exception.code, 'INVALID_TRANSITION')

        api = self.rider_client.post(
            f'/user_management/deliveryman/deliveries/{delivery.public_id}/logistics/',
            {'status': 'assigned'},
            format='json',
        )
        self.assertEqual(api.status_code, status.HTTP_409_CONFLICT)
