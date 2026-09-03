from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from service_area.models import ServiceArea, ServiceAreaRequest
from service_area.services.verification import LOW_LOCATION_ACCURACY, check_service_area
from user_management.models import (
    AdminProfile,
    CustomerDeliveryPlace,
    CustomerLocationSettings,
    CustomerProfile,
    MealDeliveryPreference,
)
from user_management.services.delivery_place import (
    ADDRESS_LIMIT_REACHED,
    LOCATION_ALREADY_EXISTS,
    DeliveryPlaceError,
    create_delivery_place,
    update_delivery_place,
)
from user_management.services.delivery_preference import (
    resolve_delivery_address,
    set_meal_delivery_preferences,
)


class CustomerLocationAPITests(APITestCase):
    def setUp(self):
        CustomerLocationSettings.load()
        settings_obj = CustomerLocationSettings.load()
        settings_obj.duplicate_radius_km = Decimal('0.50')
        settings_obj.max_active_delivery_places = 3
        settings_obj.location_refresh_interval_hours = 24
        settings_obj.save()

        self.user = User.objects.create_user(
            username='loc_cust',
            email='loc@example.com',
            password='StrongPassword123',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1733333333',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.pref_url = reverse('user_management:customer-location-preference')
        self.refresh_url = reverse('user_management:customer-location-preference-refresh')
        self.save_url = reverse('user_management:customer-location-preference-save-as-place')
        self.guest_url = reverse('user_management:customer-location-guest-offer')
        self.guest_decline_url = reverse(
            'user_management:customer-location-guest-offer-decline'
        )
        self.places_url = reverse('user_management:customer-delivery-place-list')
        self.prefs_url = reverse('user_management:customer-delivery-preferences')

    def test_geo_source_saves(self):
        coords = {
            'gps': ('22.350000', '91.840000'),
            'manual': ('22.360000', '91.850000'),
            'map_pin': ('22.370000', '91.860000'),
            'search': ('22.380000', '91.870000'),
        }
        for source, (lat, lng) in coords.items():
            CustomerDeliveryPlace.objects.filter(customer_profile=self.profile).delete()
            response = self.client.post(
                self.places_url,
                {
                    'label': f'{source}-place',
                    'full_address': f'Addr {source}',
                    'latitude': lat,
                    'longitude': lng,
                    'location_source': source,
                },
                format='json',
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['location_source'], source)

    def test_gps_without_coords_rejected(self):
        response = self.client.post(
            self.places_url,
            {
                'label': 'Bad',
                'full_address': 'Somewhere',
                'location_source': 'gps',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_on_create(self):
        create_delivery_place(
            self.profile,
            label='Home',
            full_address='Chawkbazar',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            location_source='gps',
        )
        with self.assertRaises(DeliveryPlaceError) as ctx:
            create_delivery_place(
                self.profile,
                label='Home2',
                full_address='Near',
                latitude=Decimal('22.357900'),
                longitude=Decimal('91.846300'),
                location_source='gps',
            )
        self.assertEqual(ctx.exception.code, LOCATION_ALREADY_EXISTS)

    def test_update_self_exclude(self):
        place = create_delivery_place(
            self.profile,
            label='Home',
            full_address='Chawkbazar',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            location_source='gps',
        )
        updated = update_delivery_place(
            place,
            latitude=Decimal('22.357900'),
            longitude=Decimal('91.846300'),
        )
        self.assertEqual(updated.latitude, Decimal('22.357900'))

    def test_update_colliding_with_other_place(self):
        home = create_delivery_place(
            self.profile,
            label='Home',
            full_address='A',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            location_source='gps',
        )
        office = create_delivery_place(
            self.profile,
            label='Office',
            full_address='B',
            latitude=Decimal('22.370000'),
            longitude=Decimal('91.860000'),
            location_source='gps',
        )
        with self.assertRaises(DeliveryPlaceError) as ctx:
            update_delivery_place(
                office,
                latitude=home.latitude,
                longitude=home.longitude,
            )
        self.assertEqual(ctx.exception.code, LOCATION_ALREADY_EXISTS)

    def test_outside_radius_allowed(self):
        create_delivery_place(
            self.profile,
            label='Home',
            full_address='A',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            location_source='gps',
        )
        place = create_delivery_place(
            self.profile,
            label='Far',
            full_address='B',
            latitude=Decimal('22.400000'),
            longitude=Decimal('91.900000'),
            location_source='gps',
        )
        self.assertEqual(place.label, 'Far')

    def test_address_limit_and_admin_raise(self):
        for i in range(3):
            create_delivery_place(
                self.profile,
                label=f'P{i}',
                full_address=f'A{i}',
                latitude=Decimal('22.30') + Decimal(i) * Decimal('0.02'),
                longitude=Decimal('91.80') + Decimal(i) * Decimal('0.02'),
                location_source='manual',
            )
        response = self.client.post(
            self.places_url,
            {
                'label': 'Overflow',
                'full_address': 'Too many',
                'latitude': '22.450000',
                'longitude': '91.950000',
                'location_source': 'manual',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['error_code'], ADDRESS_LIMIT_REACHED)

        settings_obj = CustomerLocationSettings.load()
        settings_obj.max_active_delivery_places = 5
        settings_obj.save()
        ok = self.client.post(
            self.places_url,
            {
                'label': 'Fourth',
                'full_address': 'OK',
                'latitude': '22.460000',
                'longitude': '91.960000',
                'location_source': 'manual',
            },
            format='json',
        )
        self.assertEqual(ok.status_code, 201, ok.data)

    def test_grandfather_above_lower_limit(self):
        settings_obj = CustomerLocationSettings.load()
        settings_obj.max_active_delivery_places = 5
        settings_obj.save()
        for i in range(4):
            create_delivery_place(
                self.profile,
                label=f'G{i}',
                full_address=f'G{i}',
                latitude=Decimal('22.20') + Decimal(i) * Decimal('0.02'),
                longitude=Decimal('91.70') + Decimal(i) * Decimal('0.02'),
                location_source='manual',
            )
        settings_obj.max_active_delivery_places = 3
        settings_obj.save()
        listing = self.client.get(self.places_url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 4)
        blocked = self.client.post(
            self.places_url,
            {
                'label': 'Extra',
                'full_address': 'No',
                'latitude': '22.500000',
                'longitude': '92.000000',
                'location_source': 'manual',
            },
            format='json',
        )
        self.assertEqual(blocked.status_code, 422)
        self.assertEqual(blocked.data['error_code'], ADDRESS_LIMIT_REACHED)

    def test_refresh_detected_only_and_save(self):
        save = self.client.post(
            self.save_url,
            {
                'label': 'Home',
                'full_address': 'Chawkbazar',
                'latitude': '22.357825',
                'longitude': '91.846267',
                'location_source': 'gps',
            },
            format='json',
        )
        self.assertEqual(save.status_code, 201, save.data)
        saved_lat = save.data['saved']['latitude']

        refresh = self.client.patch(
            self.refresh_url,
            {
                'latitude': '22.370000',
                'longitude': '91.860000',
                'accuracy': '20',
                'location_name': 'Office area',
                'source': 'gps',
            },
            format='json',
        )
        self.assertEqual(refresh.status_code, 200, refresh.data)
        self.assertEqual(str(refresh.data['detected']['latitude']), '22.370000')
        self.assertEqual(refresh.data['saved']['latitude'], saved_lat)

        get_resp = self.client.get(self.pref_url)
        self.assertTrue(get_resp.data['exists'])
        self.assertIn('can_refresh', get_resp.data)

    @override_settings(SERVICE_AREA_ACCURACY_THRESHOLD_M=500)
    def test_accuracy_warning_on_refresh(self):
        response = self.client.patch(
            self.refresh_url,
            {
                'latitude': '22.357825',
                'longitude': '91.846267',
                'accuracy': '600',
                'source': 'gps',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('warning_code'), LOW_LOCATION_ACCURACY)

        ok = self.client.patch(
            self.refresh_url,
            {
                'latitude': '22.357825',
                'longitude': '91.846267',
                'accuracy': '187',
                'source': 'gps',
            },
            format='json',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertIsNone(ok.data.get('warning_code'))

    def test_save_does_not_change_meal_defaults(self):
        home = create_delivery_place(
            self.profile,
            label='Home',
            full_address='Home addr',
            latitude=Decimal('22.300000'),
            longitude=Decimal('91.800000'),
            location_source='manual',
        )
        set_meal_delivery_preferences(
            self.profile,
            lunch_place=home,
            dinner_place=home,
        )
        response = self.client.post(
            self.save_url,
            {
                'label': 'Office',
                'full_address': 'Office',
                'latitude': '22.400000',
                'longitude': '91.900000',
                'location_source': 'gps',
                'set_lunch_default': False,
                'set_dinner_default': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        pref = MealDeliveryPreference.objects.get(customer_profile=self.profile)
        self.assertEqual(pref.lunch_place_id, home.pk)
        self.assertEqual(pref.dinner_place_id, home.pk)

    def test_explicit_lunch_flag(self):
        response = self.client.post(
            self.save_url,
            {
                'label': 'Office',
                'full_address': 'Office',
                'latitude': '22.400000',
                'longitude': '91.900000',
                'location_source': 'gps',
                'set_lunch_default': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        pref = MealDeliveryPreference.objects.get(customer_profile=self.profile)
        self.assertEqual(str(pref.lunch_place.public_id), response.data['place']['public_id'])
        self.assertIsNone(pref.dinner_place_id)

    def test_guest_offer_accept_and_blocks(self):
        ServiceAreaRequest.objects.create(
            guest_session_id='guest-session-1',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            detected_location_name='Chawkbazar',
            formatted_address='Chawkbazar, Chattogram',
            is_serviceable=True,
            request_kind=ServiceAreaRequest.RequestKind.CHECK,
        )
        offer = self.client.get(self.guest_url, {'guest_session_id': 'guest-session-1'})
        self.assertEqual(offer.status_code, 200)
        self.assertTrue(offer.data['exists'])
        self.assertEqual(offer.data['status'], 'pending')

        accept = self.client.post(
            self.guest_url,
            {
                'guest_session_id': 'guest-session-1',
                'label': 'From guest',
                'full_address': 'Chawkbazar, Chattogram',
            },
            format='json',
        )
        self.assertEqual(accept.status_code, 201, accept.data)
        self.assertEqual(accept.data['place']['location_source'], 'guest_migration')
        self.assertTrue(accept.data['location_confirmed'])
        self.assertTrue(accept.data['has_saved_location'])

        # After accept, offer is consumed (no re-prompt on "re-login" GET)
        offer_again = self.client.get(self.guest_url, {'guest_session_id': 'guest-session-1'})
        self.assertEqual(offer_again.status_code, 200)
        self.assertFalse(offer_again.data['exists'])
        self.assertEqual(offer_again.data['status'], 'accepted')

        # Duplicate accept blocked as already resolved
        blocked = self.client.post(
            self.guest_url,
            {
                'guest_session_id': 'guest-session-1',
                'label': 'Dup',
                'full_address': 'Chawkbazar, Chattogram',
            },
            format='json',
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.data['error_code'], 'GUEST_OFFER_ALREADY_RESOLVED')

        empty = self.client.get(self.guest_url, {'guest_session_id': 'missing'})
        self.assertEqual(empty.status_code, 200)
        self.assertFalse(empty.data['exists'])
        self.assertEqual(empty.data['status'], 'none')

    def test_guest_offer_decline_persists(self):
        ServiceAreaRequest.objects.create(
            guest_session_id='guest-decline-1',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            detected_location_name='Chawkbazar',
            formatted_address='Chawkbazar, Chattogram',
            is_serviceable=True,
            request_kind=ServiceAreaRequest.RequestKind.CHECK,
        )
        places_before = CustomerDeliveryPlace.objects.filter(
            customer_profile=self.profile
        ).count()

        decline = self.client.post(
            self.guest_decline_url,
            {'guest_session_id': 'guest-decline-1'},
            format='json',
        )
        self.assertEqual(decline.status_code, 200, decline.data)
        self.assertFalse(decline.data['exists'])
        self.assertEqual(decline.data['status'], 'declined')
        self.assertEqual(
            CustomerDeliveryPlace.objects.filter(customer_profile=self.profile).count(),
            places_before,
        )

        offer = self.client.get(self.guest_url, {'guest_session_id': 'guest-decline-1'})
        self.assertEqual(offer.status_code, 200)
        self.assertFalse(offer.data['exists'])
        self.assertEqual(offer.data['status'], 'declined')

        # Idempotent decline
        decline_again = self.client.post(
            self.guest_decline_url,
            {'guest_session_id': 'guest-decline-1'},
            format='json',
        )
        self.assertEqual(decline_again.status_code, 200)
        self.assertEqual(decline_again.data['status'], 'declined')

    def test_guest_offer_suppressed_when_duplicate_place(self):
        create_delivery_place(
            self.profile,
            label='Home',
            full_address='Chawkbazar',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            location_source='gps',
        )
        ServiceAreaRequest.objects.create(
            guest_session_id='guest-dup-1',
            latitude=Decimal('22.357900'),
            longitude=Decimal('91.846300'),
            detected_location_name='Near home',
            formatted_address='Near home',
            is_serviceable=True,
            request_kind=ServiceAreaRequest.RequestKind.CHECK,
        )
        offer = self.client.get(self.guest_url, {'guest_session_id': 'guest-dup-1'})
        self.assertEqual(offer.status_code, 200)
        self.assertFalse(offer.data['exists'])
        self.assertEqual(offer.data['status'], 'suppressed')

    def test_guest_offer_pending_first_time(self):
        ServiceAreaRequest.objects.create(
            guest_session_id='guest-pending-1',
            latitude=Decimal('22.400000'),
            longitude=Decimal('91.900000'),
            detected_location_name='Far',
            formatted_address='Far address',
            is_serviceable=True,
            request_kind=ServiceAreaRequest.RequestKind.CHECK,
        )
        offer = self.client.get(self.guest_url, {'guest_session_id': 'guest-pending-1'})
        self.assertEqual(offer.status_code, 200)
        self.assertTrue(offer.data['exists'])
        self.assertEqual(offer.data['status'], 'pending')

    def test_location_confirmation_flags_and_clear(self):
        empty = self.client.get(self.pref_url)
        self.assertEqual(empty.status_code, 200)
        self.assertFalse(empty.data.get('location_confirmed', False))
        self.assertFalse(empty.data.get('has_saved_location', False))

        save = self.client.post(
            self.save_url,
            {
                'label': 'Home',
                'full_address': 'Chawkbazar',
                'latitude': '22.357825',
                'longitude': '91.846267',
                'location_source': 'gps',
            },
            format='json',
        )
        self.assertEqual(save.status_code, 201, save.data)
        self.assertTrue(save.data['location_confirmed'])
        self.assertTrue(save.data['has_saved_location'])

        me = self.client.get(reverse('user_management:me'))
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data['location_confirmation']['location_confirmed'])
        self.assertTrue(me.data['location_confirmation']['has_saved_location'])

        cleared = self.client.delete(self.pref_url)
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.data['location_confirmed'])
        self.assertFalse(cleared.data['has_saved_location'])

        me_after = self.client.get(reverse('user_management:me'))
        self.assertEqual(me_after.status_code, 200)
        self.assertFalse(me_after.data['location_confirmation']['location_confirmed'])

    def test_guest_check_creates_no_place(self):
        before = CustomerDeliveryPlace.objects.count()
        check_service_area(
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            guest_session_id='guest-only',
            customer_profile=None,
        )
        self.assertEqual(CustomerDeliveryPlace.objects.count(), before)

    def test_check_saved_location_hint_authenticated(self):
        ServiceArea.objects.create(
            name='Test Hub',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            radius_km=Decimal('5.00'),
            is_active=True,
        )
        save = self.client.post(
            self.save_url,
            {
                'label': 'Home',
                'full_address': 'Chawkbazar',
                'latitude': '22.357825',
                'longitude': '91.846267',
                'location_source': 'gps',
            },
            format='json',
        )
        self.assertEqual(save.status_code, 201, save.data)
        result = check_service_area(
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            customer_profile=self.profile,
        )
        self.assertIn('saved_location', result)
        self.assertTrue(result['saved_location']['exists'])
        self.assertEqual(
            result['saved_location']['address_id'],
            save.data['place']['public_id'],
        )

        guest = check_service_area(
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            guest_session_id='g2',
            customer_profile=None,
        )
        self.assertNotIn('saved_location', guest)

    def test_meal_resolution_unchanged(self):
        place = create_delivery_place(
            self.profile,
            label='Home',
            full_address='Home',
            latitude=Decimal('22.357825'),
            longitude=Decimal('91.846267'),
            location_source='manual',
        )
        set_meal_delivery_preferences(self.profile, lunch_place=place, dinner_place=place)
        resolved = resolve_delivery_address(
            self.profile,
            timezone.localdate(),
            'lunch',
        )
        self.assertEqual(resolved.pk, place.pk)


class CustomerLocationAdminSettingsTests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='loc_admin',
            email='locadmin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.token = Token.objects.create(user=self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.url = reverse('user_management:admin-location-settings')
        self.web_url = reverse('web_customers:location-settings')

    def test_admin_get_patch(self):
        get_resp = self.client.get(self.url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.data['max_active_delivery_places'], 3)

        patch = self.client.patch(
            self.web_url,
            {'max_active_delivery_places': 5, 'duplicate_radius_km': '0.75'},
            format='json',
        )
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(patch.data['max_active_delivery_places'], 5)
