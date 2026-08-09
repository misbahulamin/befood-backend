from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import OrderWalletSettings
from orders.services.order_service import ServiceAreaOrderError, create_meal_order
from service_area.models import ServiceArea, ServiceAreaRequest
from service_area.services.geo import haversine_km
from service_area.services.matching import match_service_areas
from service_area.services.verification import (
    DELIVERY_LOCATION_REQUIRED,
    LOW_LOCATION_ACCURACY,
    SERVICE_AREA_UNAVAILABLE,
    ServiceAreaError,
    assert_customer_order_serviceable,
    assert_serviceable,
    check_service_area,
    record_demand,
)
from user_management.models import AdminProfile, CustomerDeliveryPlace, CustomerProfile
from user_management.services.delivery_preference import set_meal_delivery_preferences


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class HaversineGeoTests(TestCase):
    def test_chattogram_scale_distance(self):
        # Roughly GEC → Chawkbazar-ish points used in product examples.
        distance = haversine_km(
            Decimal('22.3569'),
            Decimal('91.7832'),
            Decimal('22.3401'),
            Decimal('91.8301'),
        )
        self.assertGreater(distance, Decimal('3'))
        self.assertLess(distance, Decimal('7'))

    def test_same_point_zero(self):
        distance = haversine_km(22.35, 91.82, 22.35, 91.82)
        self.assertEqual(distance, Decimal('0.0000'))


class MatchingServiceTests(TestCase):
    def setUp(self):
        self.chawkbazar = ServiceArea.objects.create(
            name='Chawkbazar Hub',
            latitude=Decimal('22.340100'),
            longitude=Decimal('91.830100'),
            radius_km=Decimal('5.00'),
            is_active=True,
        )
        self.agrabad = ServiceArea.objects.create(
            name='Agrabad Hub',
            latitude=Decimal('22.326500'),
            longitude=Decimal('91.812300'),
            radius_km=Decimal('4.00'),
            is_active=True,
        )

    def test_inside_radius_serviceable(self):
        # Point near Agrabad hub.
        result = match_service_areas(Decimal('22.3300'), Decimal('91.8150'))
        self.assertTrue(result.service_available)
        self.assertEqual(result.matched_area.id, self.agrabad.id)
        self.assertLessEqual(result.distance_km, self.agrabad.radius_km)

    def test_outside_all_radii(self):
        result = match_service_areas(Decimal('22.4500'), Decimal('91.9000'))
        self.assertFalse(result.service_available)
        self.assertIsNone(result.matched_area)
        self.assertIsNotNone(result.nearest_area)
        self.assertGreater(result.distance_km, Decimal('5'))

    def test_multi_hub_picks_nearest_covering(self):
        # Place clearly closer to Agrabad and inside its 4km.
        result = match_service_areas(Decimal('22.3280'), Decimal('91.8140'))
        self.assertTrue(result.service_available)
        self.assertEqual(result.matched_area.id, self.agrabad.id)

    def test_inactive_hub_ignored(self):
        self.agrabad.is_active = False
        self.agrabad.save(update_fields=['is_active'])
        self.chawkbazar.is_active = False
        self.chawkbazar.save(update_fields=['is_active'])
        only = ServiceArea.objects.create(
            name='Inactive Nearby',
            latitude=Decimal('22.3280'),
            longitude=Decimal('91.8140'),
            radius_km=Decimal('10.00'),
            is_active=False,
        )
        result = match_service_areas(Decimal('22.3280'), Decimal('91.8140'))
        self.assertFalse(result.service_available)
        self.assertIsNone(result.nearest_area)
        self.assertNotEqual(result.matched_area, only)

    def test_no_active_hubs(self):
        ServiceArea.objects.all().update(is_active=False)
        result = match_service_areas(Decimal('22.35'), Decimal('91.82'))
        self.assertFalse(result.service_available)
        self.assertIsNone(result.nearest_area)


@override_settings(SERVICE_AREA_ACCURACY_THRESHOLD_M=500)
class VerificationServiceTests(TestCase):
    def setUp(self):
        self.hub = ServiceArea.objects.create(
            name='Chawkbazar Hub',
            latitude=Decimal('22.340100'),
            longitude=Decimal('91.830100'),
            radius_km=Decimal('8.00'),
            is_active=True,
        )

    def test_check_persists_history_and_null_name_ok(self):
        result = check_service_area(
            latitude=Decimal('22.3500'),
            longitude=Decimal('91.8200'),
            accuracy=Decimal('18'),
            location_name=None,
            guest_session_id='guest-abc',
        )
        self.assertTrue(result['verified'])
        self.assertTrue(result['service_available'])
        self.assertIsNone(result['customer_location']['location_name'])
        self.assertEqual(ServiceAreaRequest.objects.count(), 1)
        row = ServiceAreaRequest.objects.get()
        self.assertEqual(row.guest_session_id, 'guest-abc')
        self.assertEqual(row.request_kind, ServiceAreaRequest.RequestKind.CHECK)

    def test_low_accuracy_warning(self):
        result = check_service_area(
            latitude=Decimal('22.3500'),
            longitude=Decimal('91.8200'),
            accuracy=Decimal('2500'),
        )
        self.assertFalse(result['location_reliable'])
        self.assertEqual(result['warning_code'], LOW_LOCATION_ACCURACY)

    def test_demand_does_not_grant_serviceability(self):
        result = record_demand(
            latitude=Decimal('22.4500'),
            longitude=Decimal('91.9000'),
            location_name='Halishahar',
            guest_session_id='guest-demand',
        )
        self.assertFalse(result['service_available'])
        row = ServiceAreaRequest.objects.get()
        self.assertEqual(row.request_kind, ServiceAreaRequest.RequestKind.DEMAND)
        self.assertFalse(row.is_serviceable)

    def test_assert_serviceable_rejects_outside(self):
        with self.assertRaises(Exception) as ctx:
            assert_serviceable(Decimal('22.4500'), Decimal('91.9000'))
        self.assertEqual(ctx.exception.code, SERVICE_AREA_UNAVAILABLE)


class ServiceAreaAPITests(APITestCase):
    def setUp(self):
        self.hub = ServiceArea.objects.create(
            name='Chawkbazar Hub',
            latitude=Decimal('22.340100'),
            longitude=Decimal('91.830100'),
            radius_km=Decimal('8.00'),
            is_active=True,
        )
        self.check_url = '/api/v1/service-areas/check/'
        self.demand_url = '/api/v1/service-areas/demand/'

        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='sa_admin',
            email='sa_admin@example.com',
            password='StrongPassword123',
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.customer_user = User.objects.create_user(
            username='sa_customer',
            email='sa_customer@example.com',
            password='StrongPassword123',
        )
        self.customer_user.groups.add(customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345678',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

    def test_guest_check(self):
        response = self.client.post(
            self.check_url,
            {
                'latitude': '22.3500',
                'longitude': '91.8200',
                'accuracy': '18',
                'location_name': 'GEC Circle, Chattogram',
                'guest_session_id': 'g-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['service_available'])
        self.assertEqual(
            response.data['customer_location']['location_name'],
            'GEC Circle, Chattogram',
        )
        self.assertEqual(response.data['matched_service_area']['name'], 'Chawkbazar Hub')

    def test_auth_customer_check_stores_profile(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        response = self.client.post(
            self.check_url,
            {'latitude': '22.3500', 'longitude': '91.8200'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = ServiceAreaRequest.objects.get()
        self.assertEqual(row.customer_profile_id, self.customer_profile.id)

    def test_validation_error_invalid_lat(self):
        response = self.client.post(
            self.check_url,
            {'latitude': '120', 'longitude': '91.82'},
            format='json',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY),
        )

    def test_demand_endpoint(self):
        response = self.client.post(
            self.demand_url,
            {
                'latitude': '22.4500',
                'longitude': '91.9000',
                'location_name': 'Halishahar',
            },
            format='json',
            HTTP_X_GUEST_SESSION_ID='header-guest',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = ServiceAreaRequest.objects.get()
        self.assertEqual(row.request_kind, 'demand')
        self.assertEqual(row.guest_session_id, 'header-guest')

    def test_admin_crud_and_permissions(self):
        list_url = '/api/v1/web/service-areas/'
        denied = self.client.get(list_url)
        self.assertIn(denied.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        denied_customer = self.client.get(list_url)
        self.assertEqual(denied_customer.status_code, status.HTTP_403_FORBIDDEN)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        create = self.client.post(
            list_url,
            {
                'name': 'GEC Hub',
                'latitude': '22.3590',
                'longitude': '91.8210',
                'radius_km': '3.00',
                'description': 'Test hub',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        public_id = create.data['public_id']

        patch = self.client.patch(
            f'{list_url}{public_id}/',
            {'radius_km': '3.50'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(patch.data['radius_km']), Decimal('3.50'))

        deactivate = self.client.post(
            f'{list_url}{public_id}/status/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(deactivate.status_code, status.HTTP_200_OK)
        self.assertFalse(deactivate.data['is_active'])

    def test_admin_analytics_summary(self):
        check_service_area(
            latitude=Decimal('22.4500'),
            longitude=Decimal('91.9000'),
            location_name='Halishahar',
        )
        check_service_area(
            latitude=Decimal('22.4501'),
            longitude=Decimal('91.9001'),
            location_name='Halishahar',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get('/api/v1/web/service-areas/requests/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['area_name'] for row in response.data['top_non_serviceable_areas']]
        self.assertIn('Halishahar', names)

    def test_admin_rejects_unsupported_filter(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get('/api/v1/web/service-areas/requests/?foo=1')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error_code'], 'UNSUPPORTED_FILTER')


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SERVICE_AREA_ORDER_GATE_ENABLED=True,
)
class OrderServiceAreaGateTests(TestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='gate_customer',
            email='gate_customer@example.com',
            password='StrongPassword123',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1799999999',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        from wallet.models import Wallet

        settings_obj, _ = OrderWalletSettings.objects.get_or_create(pk=1)
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()
        Wallet.objects.create(customer=self.profile, balance=Decimal('5000.00'))
        self.meal = MealCategory.objects.create(
            meal_name='Daily Lunch',
            total_price=Decimal('180.00'),
            meal_thumbnail=make_test_image('daily-gate.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        self.hub = ServiceArea.objects.create(
            name='Chawkbazar Hub',
            latitude=Decimal('22.340100'),
            longitude=Decimal('91.830100'),
            radius_km=Decimal('10.00'),
            is_active=True,
        )

    def _place(self, lat, lng, label='Home'):
        place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.profile,
            label=label,
            full_address=f'{label} address',
            city='Chattogram',
            area=label,
            latitude=lat,
            longitude=lng,
        )
        set_meal_delivery_preferences(self.profile, lunch_place=place, dinner_place=place)
        return place

    def test_serviceable_allows_order(self):
        self._place(Decimal('22.3500'), Decimal('91.8200'))
        order = create_meal_order(self.profile, self.meal)
        self.assertIsNotNone(order.id)

    def test_unserviceable_rejects_order(self):
        self._place(Decimal('22.5000'), Decimal('92.0000'))
        with self.assertRaises(ServiceAreaOrderError) as ctx:
            create_meal_order(self.profile, self.meal)
        self.assertEqual(ctx.exception.code, SERVICE_AREA_UNAVAILABLE)

    def test_missing_coordinates_reject(self):
        place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.profile,
            label='NoCoords',
            full_address='Somewhere',
            latitude=None,
            longitude=None,
        )
        set_meal_delivery_preferences(self.profile, lunch_place=place, dinner_place=place)
        with self.assertRaises(ServiceAreaOrderError) as ctx:
            create_meal_order(self.profile, self.meal)
        self.assertEqual(ctx.exception.code, DELIVERY_LOCATION_REQUIRED)

    def test_hub_deactivated_after_check_rejects(self):
        self._place(Decimal('22.3500'), Decimal('91.8200'))
        check_service_area(latitude=Decimal('22.3500'), longitude=Decimal('91.8200'))
        self.hub.is_active = False
        self.hub.save(update_fields=['is_active'])
        with self.assertRaises(ServiceAreaOrderError):
            create_meal_order(self.profile, self.meal)

    def test_assert_ignores_client_flags_via_coords_only(self):
        self._place(Decimal('22.5000'), Decimal('92.0000'))
        with self.assertRaises(ServiceAreaError) as ctx:
            assert_customer_order_serviceable(self.profile, 'lunch')
        self.assertEqual(ctx.exception.code, SERVICE_AREA_UNAVAILABLE)
