from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from user_management.models import CustomerProfile
from user_management.services.email_verification import generate_uid, generate_token


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CustomerAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('user_management:customer-register')
        self.login_url = reverse('user_management:login')
        self.resend_url = reverse('user_management:resend-verification')
        self.me_url = reverse('user_management:me')
        self.logout_url = reverse('user_management:logout')

    def registration_payload(self, **overrides):
        payload = {
            'email': 'customer@example.com',
            'first_name': 'Rahim',
            'last_name': 'Uddin',
            'phone': '1712345678',
            'occupation': 'student',
            'is_bachelor': True,
            'password': 'StrongPassword123',
        }
        payload.update(overrides)
        return payload

    def register_customer(self):
        return self.client.post(self.register_url, self.registration_payload(), format='json')

    def verify_customer(self, user):
        uid = generate_uid(user)
        token = generate_token(user)
        return self.client.get(reverse('user_management:verify-email', kwargs={'uidb64': uid, 'token': token}))

    def login_customer(self, email='customer@example.com', password='StrongPassword123'):
        return self.client.post(self.login_url, {'email': email, 'password': password}, format='json')

    def test_registration_success_creates_inactive_user(self):
        response = self.register_customer()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='customer@example.com')
        self.assertFalse(user.is_active)

    def test_registration_creates_customer_profile(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        self.assertTrue(hasattr(user, 'customer_profile'))
        self.assertEqual(user.customer_profile.phone, '1712345678')

    def test_registration_assigns_customer_group(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        self.assertTrue(user.groups.filter(name='CUSTOMER').exists())

    def test_registration_sends_verification_email(self):
        self.register_customer()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Activate your Befood-Bachelors E-Food account', mail.outbox[0].subject)

    def test_duplicate_email_is_blocked(self):
        self.register_customer()
        response = self.client.post(self.register_url, self.registration_payload(phone='1999999999'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)

    def test_duplicate_phone_is_blocked(self):
        self.register_customer()
        response = self.client.post(self.register_url, self.registration_payload(email='other@example.com'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_invalid_phone_is_blocked(self):
        response = self.client.post(self.register_url, self.registration_payload(phone='17abc'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_invalid_occupation_is_blocked(self):
        response = self.client.post(self.register_url, self.registration_payload(occupation='invalid'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('occupation', response.data)

    def test_login_before_email_verification_is_blocked(self):
        self.register_customer()
        response = self.login_customer()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Please verify your email before login.')

    def test_email_verification_activates_user(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        response = self.verify_customer(user)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_email_verification_marks_profile_verified(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        self.verify_customer(user)
        profile = user.customer_profile
        profile.refresh_from_db()
        self.assertTrue(profile.is_email_verified)
        self.assertIsNotNone(profile.email_verified_at)

    def test_login_after_verification_returns_token(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        self.verify_customer(user)
        response = self.login_customer()
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_resend_verification_works_for_unverified_user(self):
        self.register_customer()
        response = self.client.post(self.resend_url, {'email': 'customer@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Verification email has been sent again.')

    def test_already_verified_user_gets_proper_resend_response(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        self.verify_customer(user)
        response = self.client.post(self.resend_url, {'email': 'customer@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'This email is already verified.')

    def test_logout_deletes_token(self):
        self.register_customer()
        user = User.objects.get(email='customer@example.com')
        self.verify_customer(user)
        login_response = self.login_customer()
        token = login_response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Logged out successfully.')
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_minimal_registration_email_password_only(self):
        response = self.client.post(
            self.register_url,
            {'email': 'minimal@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='minimal@example.com')
        self.assertFalse(user.is_active)
        self.assertEqual(user.first_name, '')
        self.assertEqual(user.last_name, '')
        profile = user.customer_profile
        self.assertIsNone(profile.phone)
        self.assertIsNone(profile.occupation)
        self.assertIsNone(profile.is_bachelor)
        self.assertTrue(user.groups.filter(name='CUSTOMER').exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_verified_incomplete_profile_can_login(self):
        self.client.post(
            self.register_url,
            {'email': 'incomplete@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        user = User.objects.get(email='incomplete@example.com')
        self.verify_customer(user)
        response = self.login_customer(email='incomplete@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertIn('onboarding_completion', response.data)
        self.assertFalse(response.data['onboarding_completion']['completed'])
        self.assertIn('phone', response.data['onboarding_completion']['missing_fields'])

    def test_me_includes_onboarding_completion(self):
        self.client.post(
            self.register_url,
            {'email': 'meuser@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        user = User.objects.get(email='meuser@example.com')
        self.verify_customer(user)
        login = self.login_customer(email='meuser@example.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login.data["token"]}')
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('onboarding_completion', response.data)
        self.assertFalse(response.data['onboarding_completion']['completed'])
        self.assertIn('first_name', response.data['onboarding_completion']['missing_fields'])

    def test_multiple_customers_without_phone_allowed(self):
        self.client.post(
            self.register_url,
            {'email': 'nophone1@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        response = self.client.post(
            self.register_url,
            {'email': 'nophone2@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CustomerProfile.objects.filter(phone__isnull=True).count(), 2)

    def test_privileged_fields_ignored_at_registration(self):
        response = self.client.post(
            self.register_url,
            {
                'email': 'priv@example.com',
                'password': 'StrongPassword123',
                'is_email_verified': True,
                'is_active': True,
                'profile_completed': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='priv@example.com')
        self.assertFalse(user.is_active)
        self.assertFalse(user.customer_profile.is_email_verified)
        self.assertFalse(user.customer_profile.profile_completed)
