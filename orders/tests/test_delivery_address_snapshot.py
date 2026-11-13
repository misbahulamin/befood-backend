from django.contrib.auth.models import User
from django.test import TestCase

from orders.services.delivery_address import snapshot_fields_from_place
from user_management.models import CustomerDeliveryPlace, CustomerProfile


class SnapshotFieldsFromPlaceTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username='snap_cust',
            email='snap_cust@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.profile = CustomerProfile.objects.create(
            user=user,
            phone='1719000001',
            is_email_verified=True,
        )

    def test_place_with_building_floor_flat(self):
        place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.profile,
            label='Home',
            full_address='Mcs tower,muradpur Chittagong',
            area='Muradpur',
            city='Chittagong',
            building_name='Me likely hostel',
            floor='5',
            flat_number='619',
        )
        fields = snapshot_fields_from_place(place)
        self.assertEqual(fields['delivery_full_address_snapshot'], place.full_address)
        self.assertEqual(fields['delivery_building_name_snapshot'], 'Me likely hostel')
        self.assertEqual(fields['delivery_floor_snapshot'], '5')
        self.assertEqual(fields['delivery_flat_number_snapshot'], '619')
        self.assertEqual(fields['delivery_place'], place)

    def test_none_place_returns_empty_strings(self):
        fields = snapshot_fields_from_place(None)
        self.assertIsNone(fields['delivery_place'])
        self.assertEqual(fields['delivery_building_name_snapshot'], '')
        self.assertEqual(fields['delivery_floor_snapshot'], '')
        self.assertEqual(fields['delivery_flat_number_snapshot'], '')
        self.assertEqual(fields['delivery_full_address_snapshot'], '')

    def test_place_without_structured_parts_uses_empty_strings(self):
        place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.profile,
            label='Home',
            full_address='Street only',
            building_name='',
            floor='',
            flat_number='',
        )
        fields = snapshot_fields_from_place(place)
        self.assertEqual(fields['delivery_building_name_snapshot'], '')
        self.assertEqual(fields['delivery_floor_snapshot'], '')
        self.assertEqual(fields['delivery_flat_number_snapshot'], '')
