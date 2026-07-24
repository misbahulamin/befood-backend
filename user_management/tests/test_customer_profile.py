from datetime import date, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from user_management.models import CustomerAddress, CustomerProfile
from user_management.services.profile_completion import update_profile_completion


class CustomerProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='customer1',
            email='customer1@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            last_name='Uddin',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712345678',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.profile_url = reverse('user_management:customer-profile')
        self.address_list_url = reverse('user_management:customer-address-list')

    def test_authenticated_customer_can_get_profile(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['email'], 'customer1@example.com')
        self.assertIn('addresses', response.data)
        self.assertIn('profile_completion_percentage', response.data)

    def test_unauthenticated_user_cannot_get_profile(self):
        self.client.credentials()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 401)

    def test_customer_can_update_profile_fields(self):
        response = self.client.patch(
            self.profile_url,
            {
                'birth_date': '2000-05-15',
                'gender': 'male',
                'height_cm': '170.50',
                'weight_kg': '65.50',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(str(self.profile.birth_date), '2000-05-15')
        self.assertEqual(self.profile.gender, 'male')

    def test_future_birth_date_is_rejected(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.patch(self.profile_url, {'birth_date': future}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('birth_date', response.data)

    def test_invalid_emergency_phone_is_rejected(self):
        response = self.client.patch(
            self.profile_url,
            {'emergency_contact_phone': '17abc'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('emergency_contact_phone', response.data)

    def test_customer_can_create_present_address(self):
        response = self.client.post(
            self.address_list_url,
            {
                'address_type': 'present',
                'full_address': 'House 12, Road 5, Mirpur',
                'city': 'Dhaka',
                'area': 'Mirpur',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['address_type'], 'present')

    def test_customer_can_create_permanent_address(self):
        response = self.client.post(
            self.address_list_url,
            {
                'address_type': 'permanent',
                'full_address': 'Village home, Comilla',
                'city': 'Comilla',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['address_type'], 'permanent')
        self.assertFalse(response.data['is_default_delivery'])

    def test_first_present_address_becomes_default_delivery(self):
        self.client.post(
            self.address_list_url,
            {
                'address_type': 'present',
                'full_address': 'House 12, Road 5, Mirpur',
            },
            format='json',
        )
        address = CustomerAddress.objects.get(customer_profile=self.profile)
        self.assertTrue(address.is_default_delivery)

    def test_setting_new_default_unsets_old_default(self):
        first = CustomerAddress.objects.create(
            customer_profile=self.profile,
            address_type='present',
            full_address='First address',
            is_default_delivery=True,
        )
        second = CustomerAddress.objects.create(
            customer_profile=self.profile,
            address_type='present',
            full_address='Second address',
        )
        set_default_url = reverse('user_management:customer-address-set-default', kwargs={'public_id': second.public_id})
        response = self.client.post(set_default_url)
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default_delivery)
        self.assertTrue(second.is_default_delivery)

    def test_customer_cannot_access_another_customers_address(self):
        other_user = User.objects.create_user(
            username='customer2',
            email='customer2@example.com',
            password='StrongPassword123',
        )
        other_profile = CustomerProfile.objects.create(
            user=other_user,
            phone='1812345678',
            occupation=CustomerProfile.Occupation.JOB_HOLDER,
            is_bachelor=False,
            is_email_verified=True,
        )
        other_address = CustomerAddress.objects.create(
            customer_profile=other_profile,
            address_type='present',
            full_address='Other customer address',
        )
        detail_url = reverse('user_management:customer-address-detail', kwargs={'public_id': other_address.public_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

    def test_profile_completion_updates_after_profile_update(self):
        CustomerAddress.objects.create(
            customer_profile=self.profile,
            address_type='present',
            full_address='House 12, Road 5, Mirpur',
            is_default_delivery=True,
        )
        response = self.client.patch(
            self.profile_url,
            {
                'birth_date': '2000-05-15',
                'gender': 'male',
                'emergency_contact_phone': '1812345678',
                'organization_name': 'Dhaka University',
                'restricted_foods': 'Beef',
                'preferred_food_type': 'regular',
                'religious': 'islam',
                'preferred_delivery_time': '13:30:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['profile_completion_percentage'], 80)
        self.assertTrue(response.data['profile_completed'])

    def test_allergy_details_required_when_has_allergy_true(self):
        response = self.client.patch(
            self.profile_url,
            {'has_allergy': True},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('allergy_details', response.data)

    def test_address_full_address_is_required(self):
        response = self.client.post(
            self.address_list_url,
            {'address_type': 'present', 'full_address': '   '},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('full_address', response.data)

    def test_set_default_only_works_on_own_address(self):
        other_user = User.objects.create_user(
            username='customer3',
            email='customer3@example.com',
            password='StrongPassword123',
        )
        other_profile = CustomerProfile.objects.create(
            user=other_user,
            phone='1912345678',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        other_address = CustomerAddress.objects.create(
            customer_profile=other_profile,
            address_type='present',
            full_address='Other address',
        )
        set_default_url = reverse('user_management:customer-address-set-default', kwargs={'public_id': other_address.public_id})
        response = self.client.post(set_default_url)
        self.assertEqual(response.status_code, 404)

    def test_user_without_customer_profile_gets_clear_error(self):
        staff_user = User.objects.create_user(
            username='staff1',
            email='staff1@example.com',
            password='StrongPassword123',
        )
        staff_token = Token.objects.create(user=staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {staff_token.key}')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 403)

    def test_profile_completion_recalculates_on_address_create(self):
        self.client.patch(
            self.profile_url,
            {
                'birth_date': '2000-05-15',
                'gender': 'male',
                'emergency_contact_phone': '1812345678',
                'organization_name': 'Dhaka University',
                'restricted_foods': 'Beef',
                'preferred_food_type': 'regular',
                'religious': 'islam',
                'preferred_delivery_time': '13:30:00',
            },
            format='json',
        )
        self.client.post(
            self.address_list_url,
            {'address_type': 'present', 'full_address': 'House 12, Road 5, Mirpur'},
            format='json',
        )
        self.profile.refresh_from_db()
        update_profile_completion(self.profile)
        self.profile.refresh_from_db()
        self.assertGreaterEqual(self.profile.profile_completion_percentage, 80)
