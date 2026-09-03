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
        self.assertEqual(
            response.data['customer_profile']['phone'],
            '+8801712345678',
        )
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


class ProgressiveOnboardingProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='onboard1',
            email='onboard1@example.com',
            password='StrongPassword123',
            first_name='',
            last_name='',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone=None,
            occupation=None,
            is_bachelor=None,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.profile_url = reverse('user_management:customer-profile')

    def test_profile_get_includes_onboarding_completion(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('onboarding_completion', response.data)
        missing = response.data['onboarding_completion']['missing_fields']
        for field in ('first_name', 'last_name', 'phone', 'occupation', 'is_bachelor', 'gender'):
            self.assertIn(field, missing)
        self.assertFalse(response.data['onboarding_completion']['completed'])

    def test_patch_names_independently(self):
        response = self.client.patch(
            self.profile_url,
            {'first_name': 'John', 'last_name': 'Doe'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.phone)
        missing = response.data['onboarding_completion']['missing_fields']
        self.assertNotIn('first_name', missing)
        self.assertNotIn('last_name', missing)
        self.assertIn('phone', missing)

    def test_patch_phone_independently(self):
        self.client.patch(self.profile_url, {'first_name': 'John', 'last_name': 'Doe'}, format='json')
        response = self.client.patch(self.profile_url, {'phone': '1711111111'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone, '1711111111')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')

    def test_patch_demographics_independently(self):
        response = self.client.patch(
            self.profile_url,
            {'gender': 'male', 'is_bachelor': True, 'occupation': 'student'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gender, 'male')
        self.assertTrue(self.profile.is_bachelor)
        self.assertEqual(self.profile.occupation, 'student')

    def test_invalid_phone_does_not_clear_other_fields(self):
        self.client.patch(self.profile_url, {'first_name': 'John'}, format='json')
        response = self.client.patch(self.profile_url, {'phone': 'abc'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')

    def test_invalid_gender_rejected(self):
        response = self.client.patch(self.profile_url, {'gender': 'unknown'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('gender', response.data)

    def test_duplicate_phone_rejected(self):
        other = User.objects.create_user(username='other', email='other@example.com', password='StrongPassword123')
        CustomerProfile.objects.create(
            user=other,
            phone='1999999999',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        response = self.client.patch(self.profile_url, {'phone': '1999999999'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_privileged_mass_assignment_blocked(self):
        response = self.client.patch(
            self.profile_url,
            {
                'is_email_verified': False,
                'profile_completed': True,
                'profile_completion_percentage': 100,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_email_verified)
        self.assertFalse(self.profile.profile_completed)

    def test_idempotent_name_patch(self):
        payload = {'first_name': 'John', 'last_name': 'Doe'}
        self.assertEqual(self.client.patch(self.profile_url, payload, format='json').status_code, 200)
        self.assertEqual(self.client.patch(self.profile_url, payload, format='json').status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')

    def test_full_onboarding_reports_completed(self):
        response = self.client.patch(
            self.profile_url,
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '1711111111',
                'occupation': 'student',
                'is_bachelor': False,
                'gender': 'male',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['onboarding_completion']['completed'])
        self.assertEqual(response.data['onboarding_completion']['missing_fields'], [])

    def test_legacy_customer_missing_only_gender(self):
        self.user.first_name = 'Rahim'
        self.user.last_name = 'Uddin'
        self.user.save()
        self.profile.phone = '1712345678'
        self.profile.occupation = 'student'
        self.profile.is_bachelor = True
        self.profile.gender = None
        self.profile.save()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.data['onboarding_completion']['missing_fields'], ['gender'])
        self.assertFalse(response.data['onboarding_completion']['completed'])

