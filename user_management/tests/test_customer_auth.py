"""Customer auth smoke tests aligned with deferred registration + AuthSession."""

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from user_management.models import AuthSession, PendingCustomerRegistration
from user_management.services.pending_registration import (
    encode_pending_uid,
    generate_pending_link_token,
    issue_pending_otp,
)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CustomerAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.register_url = reverse('user_management:customer-register')
        self.login_url = reverse('user_management:login')
        self.resend_url = reverse('user_management:resend-verification')
        self.me_url = reverse('user_management:me')
        self.logout_url = reverse('user_management:logout')
        self.verify_otp_url = reverse('user_management:verify-email-otp')

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

    def finalize_via_otp(self, email='customer@example.com'):
        pending = PendingCustomerRegistration.objects.get(email=email)
        result = issue_pending_otp(pending, force_new=True)
        response = self.client.post(
            self.verify_otp_url,
            {'email': email, 'otp': result.plaintext_otp},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        return User.objects.get(email=email)

    def login_customer(self, email='customer@example.com', password='StrongPassword123'):
        return self.client.post(self.login_url, {'email': email, 'password': password}, format='json')

    def test_registration_creates_pending_not_user(self):
        response = self.register_customer()
        self.assertEqual(response.status_code, 201)
        self.assertFalse(User.objects.filter(email='customer@example.com').exists())
        self.assertTrue(
            PendingCustomerRegistration.objects.filter(email='customer@example.com').exists()
        )

    def test_registration_sends_verification_email(self):
        self.register_customer()
        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(mail.outbox[0].subject, r'^\d{6} is your sign-in verification code$')

    def test_duplicate_verified_email_is_blocked(self):
        self.register_customer()
        self.finalize_via_otp()
        response = self.client.post(
            self.register_url,
            self.registration_payload(phone='1999999999'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)

    def test_duplicate_phone_is_blocked(self):
        self.register_customer()
        response = self.client.post(
            self.register_url,
            self.registration_payload(email='other@example.com'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_invalid_phone_is_blocked(self):
        response = self.client.post(
            self.register_url, self.registration_payload(phone='17abc'), format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_invalid_occupation_is_blocked(self):
        response = self.client.post(
            self.register_url, self.registration_payload(occupation='invalid'), format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('occupation', response.data)

    def test_login_before_verification_is_invalid_credentials(self):
        self.register_customer()
        response = self.login_customer()
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.data)

    def test_otp_verification_creates_active_customer(self):
        self.register_customer()
        user = self.finalize_via_otp()
        self.assertTrue(user.is_active)
        self.assertTrue(user.groups.filter(name='CUSTOMER').exists())
        profile = user.customer_profile
        self.assertTrue(profile.is_email_verified)
        self.assertEqual(profile.phone, '1712345678')

    def test_login_after_verification_returns_unified_envelope(self):
        self.register_customer()
        self.finalize_via_otp()
        response = self.login_customer()
        self.assertEqual(response.status_code, 200)
        for key in ('token', 'user', 'customer_profile', 'device_token_status', 'auth_provider', 'groups'):
            self.assertIn(key, response.data)
        self.assertEqual(response.data['auth_provider'], 'email')

    def test_resend_verification_works_for_pending(self):
        self.register_customer()
        response = self.client.post(self.resend_url, {'email': 'customer@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_already_verified_user_gets_proper_resend_response(self):
        self.register_customer()
        self.finalize_via_otp()
        response = self.client.post(self.resend_url, {'email': 'customer@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'This email is already verified.')

    def test_logout_revokes_current_session(self):
        self.register_customer()
        user = self.finalize_via_otp()
        login_response = self.login_customer()
        token = login_response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Logged out successfully.')
        session = AuthSession.objects.get(key=token)
        self.assertIsNotNone(session.revoked_at)
        self.assertEqual(self.client.get(self.me_url).status_code, 401)

    def test_minimal_registration_email_password_only(self):
        response = self.client.post(
            self.register_url,
            {'email': 'minimal@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        pending = PendingCustomerRegistration.objects.get(email='minimal@example.com')
        self.assertEqual(pending.first_name, '')
        self.assertIsNone(pending.phone)
        self.assertEqual(len(mail.outbox), 1)

    def test_verified_incomplete_profile_can_login(self):
        self.client.post(
            self.register_url,
            {'email': 'incomplete@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.finalize_via_otp('incomplete@example.com')
        response = self.login_customer(email='incomplete@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertIn('onboarding_completion', response.data)
        self.assertFalse(response.data['onboarding_completion']['completed'])

    def test_me_includes_onboarding_completion(self):
        self.client.post(
            self.register_url,
            {'email': 'meuser@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.finalize_via_otp('meuser@example.com')
        login = self.login_customer(email='meuser@example.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login.data["token"]}')
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('onboarding_completion', response.data)

    def test_multiple_pending_without_phone_allowed(self):
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
        self.assertEqual(
            PendingCustomerRegistration.objects.filter(phone__isnull=True).count(),
            2,
        )

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
        self.assertFalse(User.objects.filter(email='priv@example.com').exists())
        pending = PendingCustomerRegistration.objects.get(email='priv@example.com')
        self.assertTrue(pending.password_hash)

    def test_pending_link_verification(self):
        self.register_customer()
        pending = PendingCustomerRegistration.objects.get(email='customer@example.com')
        uid = encode_pending_uid(pending)
        token = generate_pending_link_token(pending)
        response = self.client.get(
            reverse('user_management:verify-email', kwargs={'uidb64': uid, 'token': token})
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='customer@example.com')
        self.assertTrue(user.customer_profile.is_email_verified)
