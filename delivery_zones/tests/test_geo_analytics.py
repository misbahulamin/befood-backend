from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from delivery_zones.services.assignment import assign_customer_sub_location
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.geo_analytics import (
    CHURN_RANKING_MIN_ACTIVE_BASE,
    build_geo_analytics_matrix,
    parse_geo_analytics_query,
)
from delivery_zones.services.locations import create_location
from delivery_zones.services.sub_locations import create_sub_location
from delivery_zones.services.zones import assign_delivery_man, create_zone
from meals.models import MealCategory
from orders.models import CustomerSubscription, OrderDelivery
from user_management.models import AdminProfile, CustomerProfile, RiderProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _make_customer(username, phone):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        first_name=username.title(),
        is_active=True,
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    return CustomerProfile.objects.create(
        user=user, phone=phone, is_email_verified=True
    )


class GeoAnalyticsParseTests(TestCase):
    def test_missing_from_to_rejected(self):
        with self.assertRaises(DeliveryZoneError) as ctx:
            parse_geo_analytics_query({'to': '2026-01-10'})
        self.assertEqual(ctx.exception.code, 'DATE_RANGE_REQUIRED')

        with self.assertRaises(DeliveryZoneError) as ctx2:
            parse_geo_analytics_query({'from': '2026-01-01'})
        self.assertEqual(ctx2.exception.code, 'DATE_RANGE_REQUIRED')

    def test_inverted_and_too_long_range(self):
        with self.assertRaises(DeliveryZoneError) as ctx:
            parse_geo_analytics_query({'from': '2026-02-01', 'to': '2026-01-01'})
        self.assertEqual(ctx.exception.code, 'INVALID_DATE_RANGE')

        with self.assertRaises(DeliveryZoneError) as ctx2:
            parse_geo_analytics_query({'from': '2025-01-01', 'to': '2026-12-31'})
        self.assertEqual(ctx2.exception.code, 'DATE_RANGE_TOO_LONG')

    def test_unknown_filter_rejected(self):
        with self.assertRaises(DeliveryZoneError) as ctx:
            parse_geo_analytics_query(
                {'from': '2026-01-01', 'to': '2026-01-31', 'foo': '1'}
            )
        self.assertEqual(ctx.exception.code, 'UNSUPPORTED_FILTER')


class GeoAnalyticsMatrixServiceTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='DELIVERY_MAN')
        Group.objects.get_or_create(name='CUSTOMER')

        rider_user = User.objects.create_user(
            username='geo_rider',
            email='geo_rider@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            is_active=True,
        )
        self.rider = RiderProfile.objects.create(
            user=rider_user,
            phone='1719000001',
            approval_status=RiderProfile.ApprovalStatus.APPROVED,
            is_verified=True,
            is_email_verified=True,
            verified_at=timezone.now(),
        )

        self.zone1 = create_zone(name='Zone 1', code='geo-z1', priority=1)
        self.zone2 = create_zone(name='Zone 2', code='geo-z2', priority=2)
        assign_delivery_man(self.zone1, delivery_man_public_id=self.rider.public_id)

        self.loc_a = create_location(
            name='Chawkbazar', zone_public_id=self.zone1.public_id, priority=1
        )
        self.loc_b = create_location(
            name='DC Road', zone_public_id=self.zone1.public_id, priority=2
        )
        self.loc_other = create_location(
            name='Other Loc', zone_public_id=self.zone2.public_id, priority=1
        )

        self.gate_a = create_sub_location(
            name='Gate A', location_public_id=self.loc_a.public_id, priority=2
        )
        self.gate_b = create_sub_location(
            name='Gate B', location_public_id=self.loc_a.public_id, priority=3
        )
        self.dc_default = self.loc_b.sub_locations.get(is_default=True)

        self.plan = MealCategory.objects.create(
            meal_name='Geo Plan',
            total_price=Decimal('150.00'),
            meal_thumbnail=make_test_image('geo.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )

        self.start = date(2026, 1, 1)
        self.end = date(2026, 1, 31)

    def _active_sub(self, customer, started_on, *, status=CustomerSubscription.Status.ACTIVE, **extra):
        return CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=status,
            started_on=started_on,
            **extra,
        )

    def _delivery(self, subscription, service_date, meal_period, status, *, logistics_sub=None):
        return OrderDelivery.objects.create(
            subscription=subscription,
            service_date=service_date,
            meal_period=meal_period,
            status=status,
            delivery_label_snapshot='Home',
            delivery_full_address_snapshot='House',
            delivery_area_snapshot='Area',
            delivery_city_snapshot='Chattogram',
            logistics_sub_location=logistics_sub,
        )

    def test_customer_density_lifecycle_and_unassigned(self):
        c_active = _make_customer('geo_active', '1719000101')
        c_unsub = _make_customer('geo_unsub', '1719000102')
        c_unassigned = _make_customer('geo_unasg', '1719000103')

        assign_customer_sub_location(c_active, sub_location_public_id=self.gate_a.public_id)
        assign_customer_sub_location(c_unsub, sub_location_public_id=self.gate_a.public_id)

        self._active_sub(c_active, self.start - timedelta(days=10))
        self._active_sub(
            c_unsub,
            self.start - timedelta(days=20),
            status=CustomerSubscription.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancel_effective_on=self.start + timedelta(days=5),
        )

        matrix = build_geo_analytics_matrix(
            {'from': self.start.isoformat(), 'to': self.end.isoformat()}
        )
        zone = next(z for z in matrix['zones'] if z['code'] == 'geo-z1')
        loc = next(loc for loc in zone['locations'] if loc['name'] == 'Chawkbazar')
        gate = next(s for s in loc['sub_locations'] if s['name'] == 'Gate A')

        self.assertGreaterEqual(gate['customers']['total'], 2)
        self.assertGreaterEqual(gate['customers']['active'], 1)
        self.assertGreaterEqual(gate['customers']['unsubscribed'], 1)
        self.assertGreaterEqual(matrix['unassigned_customers']['total'], 1)
        self.assertIsNone(c_unassigned.delivery_sub_location_id)

    def test_location_churn_rate_and_zero_base(self):
        # 4 active-at-start + 1 churn under Gate A → rate 25% with base 4
        customers = []
        for i in range(4):
            c = _make_customer(f'geo_base_{i}', f'17190002{i:02d}')
            assign_customer_sub_location(c, sub_location_public_id=self.gate_a.public_id)
            self._active_sub(c, self.start - timedelta(days=30))
            customers.append(c)

        churned = customers[0]
        sub = churned.meal_subscriptions.get()
        sub.status = CustomerSubscription.Status.CANCELLED
        sub.cancelled_at = timezone.now()
        sub.cancel_effective_on = self.start + timedelta(days=3)
        sub.save(
            update_fields=['status', 'cancelled_at', 'cancel_effective_on', 'updated_at']
        )

        # Orphan cancel on Gate B with no active-at-start base
        orphan = _make_customer('geo_orphan', '1719000299')
        assign_customer_sub_location(orphan, sub_location_public_id=self.gate_b.public_id)
        self._active_sub(
            orphan,
            self.start + timedelta(days=1),
            status=CustomerSubscription.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancel_effective_on=self.start + timedelta(days=2),
        )

        matrix = build_geo_analytics_matrix(
            {'from': self.start.isoformat(), 'to': self.end.isoformat()}
        )
        zone = next(z for z in matrix['zones'] if z['code'] == 'geo-z1')
        loc = next(loc for loc in zone['locations'] if loc['name'] == 'Chawkbazar')
        gate_a = next(s for s in loc['sub_locations'] if s['name'] == 'Gate A')
        gate_b = next(s for s in loc['sub_locations'] if s['name'] == 'Gate B')

        self.assertEqual(gate_a['churn']['churned_count'], 1)
        self.assertEqual(gate_a['churn']['active_at_period_start'], 4)
        self.assertEqual(gate_a['churn']['churn_rate_percent'], 25.0)

        self.assertEqual(gate_b['churn']['churned_count'], 1)
        self.assertEqual(gate_b['churn']['active_at_period_start'], 0)
        self.assertEqual(gate_b['churn']['churn_rate_percent'], 0.0)

    def test_meal_volume_and_lunch_filter(self):
        c = _make_customer('geo_vol', '1719000301')
        assign_customer_sub_location(c, sub_location_public_id=self.gate_a.public_id)
        sub = self._active_sub(c, self.start - timedelta(days=5))
        self._delivery(
            sub,
            self.start + timedelta(days=1),
            'lunch',
            OrderDelivery.DeliveryStatus.DELIVERED,
            logistics_sub=self.gate_a,
        )
        self._delivery(
            sub,
            self.start + timedelta(days=1),
            'dinner',
            OrderDelivery.DeliveryStatus.SKIPPED,
            logistics_sub=self.gate_a,
        )
        # Unassigned delivery (no logistics, no customer sub on another customer)
        u = _make_customer('geo_vol_u', '1719000302')
        usub = self._active_sub(u, self.start - timedelta(days=5))
        self._delivery(
            usub,
            self.start + timedelta(days=2),
            'lunch',
            OrderDelivery.DeliveryStatus.SCHEDULED,
        )

        both = build_geo_analytics_matrix(
            {'from': self.start.isoformat(), 'to': self.end.isoformat()}
        )
        zone = next(z for z in both['zones'] if z['code'] == 'geo-z1')
        loc = next(loc for loc in zone['locations'] if loc['name'] == 'Chawkbazar')
        gate = next(s for s in loc['sub_locations'] if s['name'] == 'Gate A')
        self.assertEqual(gate['volume']['delivered'], 1)
        self.assertEqual(gate['volume']['skipped'], 1)
        self.assertEqual(gate['volume']['total'], 2)
        self.assertGreaterEqual(both['unassigned_volume']['total'], 1)

        lunch = build_geo_analytics_matrix(
            {
                'from': self.start.isoformat(),
                'to': self.end.isoformat(),
                'meal_period': 'lunch',
            }
        )
        zone_l = next(z for z in lunch['zones'] if z['code'] == 'geo-z1')
        loc_l = next(loc for loc in zone_l['locations'] if loc['name'] == 'Chawkbazar')
        gate_l = next(s for s in loc_l['sub_locations'] if s['name'] == 'Gate A')
        self.assertEqual(gate_l['volume']['delivered'], 1)
        self.assertEqual(gate_l['volume']['skipped'], 0)
        self.assertEqual(gate_l['volume']['total'], 1)

        self.assertEqual(zone['assigned_delivery_man']['first_name'], 'Rahim')
        self.assertEqual(zone['workload']['delivered'], 1)
        self.assertEqual(zone['workload']['total'], 2)

    def test_rankings_exclude_low_base_churn(self):
        # Dense DC Road: 6 customers
        for i in range(6):
            c = _make_customer(f'geo_dense_{i}', f'17190004{i:02d}')
            assign_customer_sub_location(c, sub_location_public_id=self.dc_default.public_id)
            self._active_sub(c, self.start - timedelta(days=10))

        # Thin Gate A: 1 customer, 100% churn, base 1 (< min 5)
        thin = _make_customer('geo_thin', '1719000499')
        assign_customer_sub_location(thin, sub_location_public_id=self.gate_a.public_id)
        self._active_sub(
            thin,
            self.start - timedelta(days=10),
            status=CustomerSubscription.Status.CANCELLED,
            cancelled_at=timezone.now(),
            cancel_effective_on=self.start + timedelta(days=1),
        )

        matrix = build_geo_analytics_matrix(
            {'from': self.start.isoformat(), 'to': self.end.isoformat()}
        )
        self.assertEqual(
            matrix['rankings']['churn_min_active_base'], CHURN_RANKING_MIN_ACTIVE_BASE
        )
        high_density = matrix['rankings']['highest_customer_density']
        self.assertTrue(any(r['name'] == 'DC Road' for r in high_density))
        high_churn = matrix['rankings']['highest_churn_rate']
        self.assertFalse(any(r['name'] == 'Chawkbazar' for r in high_churn))

    def test_zone_scope_filter(self):
        matrix = build_geo_analytics_matrix(
            {
                'from': self.start.isoformat(),
                'to': self.end.isoformat(),
                'zone_public_id': str(self.zone1.public_id),
            }
        )
        codes = [z['code'] for z in matrix['zones']]
        self.assertEqual(codes, ['geo-z1'])

    def test_unknown_zone_404_code(self):
        with self.assertRaises(DeliveryZoneError) as ctx:
            build_geo_analytics_matrix(
                {
                    'from': self.start.isoformat(),
                    'to': self.end.isoformat(),
                    'zone_public_id': '00000000-0000-0000-0000-000000000001',
                }
            )
        self.assertEqual(ctx.exception.code, 'ZONE_NOT_FOUND')


class GeoAnalyticsAPITests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        admin_user = User.objects.create_user(
            username='geo_admin',
            email='geo_admin@example.com',
            password='StrongPassword123',
            is_active=True,
            is_staff=True,
        )
        admin_user.groups.add(admin_group)
        self.admin = AdminProfile.objects.create(user=admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=admin_user)

        cust_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        cust_user = User.objects.create_user(
            username='geo_cust_api',
            email='geo_cust_api@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        cust_user.groups.add(cust_group)
        self.customer = CustomerProfile.objects.create(
            user=cust_user, phone='1719000501', is_email_verified=True
        )
        self.customer_token = Token.objects.create(user=cust_user)

        self.zone = create_zone(name='API Zone', code='geo-api-z', priority=1)
        self.location = create_location(
            name='API Loc', zone_public_id=self.zone.public_id, priority=1
        )
        self.sub = create_sub_location(
            name='API Gate', location_public_id=self.location.public_id, priority=2
        )
        assign_customer_sub_location(
            self.customer, sub_location_public_id=self.sub.public_id
        )

    def test_auth_and_validation(self):
        url = '/api/v1/web/delivery-zones/analytics/matrix/'
        anon = self.client.get(url, {'from': '2026-01-01', 'to': '2026-01-31'})
        self.assertEqual(anon.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        forbidden = self.client.get(url, {'from': '2026-01-01', 'to': '2026-01-31'})
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        bad = self.client.get(url)
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        ok = self.client.get(url, {'from': '2026-01-01', 'to': '2026-01-31'})
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertIn('zones', ok.data)
        self.assertIn('rankings', ok.data)
        self.assertEqual(ok.data['from'], '2026-01-01')
        self.assertEqual(ok.data['to'], '2026-01-31')

    def test_scope_and_customer_drilldown_filters(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        matrix = self.client.get(
            '/api/v1/web/delivery-zones/analytics/matrix/',
            {
                'from': '2026-01-01',
                'to': '2026-01-31',
                'zone_public_id': str(self.zone.public_id),
            },
        )
        self.assertEqual(matrix.status_code, status.HTTP_200_OK)
        self.assertEqual(len(matrix.data['zones']), 1)

        missing = self.client.get(
            '/api/v1/web/delivery-zones/analytics/matrix/',
            {
                'from': '2026-01-01',
                'to': '2026-01-31',
                'zone_public_id': '00000000-0000-0000-0000-000000000099',
            },
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

        filtered = self.client.get(
            '/api/v1/web/customers/',
            {'sub_location_public_id': str(self.sub.public_id)},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        ids = [row['public_id'] for row in filtered.data['results']]
        self.assertIn(str(self.customer.public_id), ids)

        unassigned = self.client.get(
            '/api/v1/web/customers/',
            {'has_delivery_sub_location': 'false'},
        )
        self.assertEqual(unassigned.status_code, status.HTTP_200_OK)
        unas_ids = [row['public_id'] for row in unassigned.data['results']]
        self.assertNotIn(str(self.customer.public_id), unas_ids)
