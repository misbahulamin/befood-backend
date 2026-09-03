"""Tests for deferred customer registration (pending until email verify)."""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from user_management.models import CustomerProfile, DeviceToken, PendingCustomerRegistration
from user_management.services.pending_registration import (
    cleanup_expired_pending_registrations,
    encode_pending_uid,
    generate_pending_link_token,
    issue_pending_otp,
    migrate_legacy_unverified_to_pending,
)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AUTH_OTP_TTL_SECONDS=600,
    AUTH_OTP_MAX_ATTEMPTS=5,
    AUTH_OTP_RESEND_COOLDOWN_SECONDS=60,
    AUTH_OTP_MAX_ISSUES_PER_HOUR=10,
    FRONTEND_URL='https://www.befood.com.bd',
    EMAIL_VERIFICATION_FRONTEND_PATH='/verify-email',
    PASSWORD_RESET_FRONTEND_PATH='/reset-password',
)
class DeferredCustomerRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.register_url = reverse('user_management:customer-register')
        self.login_url = reverse('user_management:login')
        self.verify_otp_url = reverse('user_management:verify-email-otp')
        self.resend_url = reverse('user_management:resend-verification')

    def _register(self, email='pending@example.com', password='StrongPassword123', **extra):
        payload = {'email': email, 'password': password, **extra}
        return self.client.post(self.register_url, payload, format='json')

    def test_register_creates_pending_only(self):
        mail.outbox.clear()
        response = self._register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['email'], 'pending@example.com')
        self.assertFalse(User.objects.filter(email__iexact='pending@example.com').exists())
        self.assertTrue(
            PendingCustomerRegistration.objects.filter(email='pending@example.com').exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(mail.outbox[0].subject, r'^\d{6} is your sign-in verification code$')
        self.assertRegex(mail.outbox[0].body, r'\b\d{6}\b')
        self.assertIn('/verify-email/', mail.outbox[0].body)

    def test_register_rejects_verified_email(self):
        user = User.objects.create_user(
            username='taken',
            email='taken@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(user=user, is_email_verified=True)
        response = self._register(email='taken@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)

    def test_reregister_updates_pending(self):
        self._register(email='again@example.com', password='StrongPassword123')
        first = PendingCustomerRegistration.objects.get(email='again@example.com')
        first_hash = first.password_hash
        with override_settings(AUTH_OTP_RESEND_COOLDOWN_SECONDS=0):
            mail.outbox.clear()
            response = self._register(email='again@example.com', password='AnotherStrongPass123')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(PendingCustomerRegistration.objects.filter(email='again@example.com').count(), 1)
        first.refresh_from_db()
        self.assertNotEqual(first.password_hash, first_hash)
        self.assertFalse(User.objects.filter(email__iexact='again@example.com').exists())

    def test_verify_otp_creates_account_and_consumes_pending(self):
        self._register(email='verifyotp@example.com')
        pending = PendingCustomerRegistration.objects.get(email='verifyotp@example.com')
        issue = issue_pending_otp(pending, force_new=True)
        otp = issue.plaintext_otp
        response = self.client.post(
            self.verify_otp_url,
            {'email': 'verifyotp@example.com', 'otp': otp},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PendingCustomerRegistration.objects.filter(email='verifyotp@example.com').exists())
        user = User.objects.get(email='verifyotp@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.customer_profile.is_email_verified)
        self.assertTrue(user.groups.filter(name='CUSTOMER').exists())
        self.assertTrue(user.check_password('StrongPassword123'))

    def test_verify_link_creates_account(self):
        self._register(email='verifylink@example.com')
        pending = PendingCustomerRegistration.objects.get(email='verifylink@example.com')
        uid = encode_pending_uid(pending)
        token = generate_pending_link_token(pending)
        response = self.client.get(
            reverse('user_management:verify-email', kwargs={'uidb64': uid, 'token': token})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PendingCustomerRegistration.objects.filter(email='verifylink@example.com').exists())
        user = User.objects.get(email='verifylink@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.customer_profile.is_email_verified)

    def test_wrong_otp_does_not_create_user(self):
        self._register(email='badotp@example.com')
        pending = PendingCustomerRegistration.objects.get(email='badotp@example.com')
        issue_pending_otp(pending, force_new=True)
        response = self.client.post(
            self.verify_otp_url,
            {'email': 'badotp@example.com', 'otp': '000000'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email__iexact='badotp@example.com').exists())

    def test_login_with_pending_only_fails(self):
        self._register(email='nologin@example.com')
        response = self.client.post(
            self.login_url,
            {'email': 'nologin@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Invalid credentials.')

    def test_login_after_verify_succeeds(self):
        self._register(email='after@example.com')
        pending = PendingCustomerRegistration.objects.get(email='after@example.com')
        otp = issue_pending_otp(pending, force_new=True).plaintext_otp
        self.client.post(
            self.verify_otp_url,
            {'email': 'after@example.com', 'otp': otp},
            format='json',
        )
        response = self.client.post(
            self.login_url,
            {'email': 'after@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_login_with_optional_device_token(self):
        self._register(email='devicetok@example.com')
        pending = PendingCustomerRegistration.objects.get(email='devicetok@example.com')
        otp = issue_pending_otp(pending, force_new=True).plaintext_otp
        self.client.post(
            self.verify_otp_url,
            {'email': 'devicetok@example.com', 'otp': otp},
            format='json',
        )
        fcm = 'b' * 140
        response = self.client.post(
            self.login_url,
            {
                'email': 'devicetok@example.com',
                'password': 'StrongPassword123',
                'device_token': fcm,
                'platform': 'android',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='devicetok@example.com')
        self.assertEqual(DeviceToken.objects.filter(user=user, token=fcm, is_active=True).count(), 1)

    def test_resend_pending_verification(self):
        self._register(email='resendp@example.com')
        with override_settings(AUTH_OTP_RESEND_COOLDOWN_SECONDS=0):
            mail.outbox.clear()
            response = self.client.post(
                self.resend_url,
                {'email': 'resendp@example.com'},
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(mail.outbox[0].subject, r'^\d{6} is your sign-in verification code$')

    def test_expired_pending_cannot_verify(self):
        self._register(email='expired@example.com')
        pending = PendingCustomerRegistration.objects.get(email='expired@example.com')
        otp = issue_pending_otp(pending, force_new=True).plaintext_otp
        PendingCustomerRegistration.objects.filter(pk=pending.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        response = self.client.post(
            self.verify_otp_url,
            {'email': 'expired@example.com', 'otp': otp},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email__iexact='expired@example.com').exists())

    def test_cleanup_expired_pending(self):
        self._register(email='cleanup@example.com')
        PendingCustomerRegistration.objects.filter(email='cleanup@example.com').update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        deleted = cleanup_expired_pending_registrations()
        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(PendingCustomerRegistration.objects.filter(email='cleanup@example.com').exists())

    def test_cleanup_management_command(self):
        self._register(email='cmdclean@example.com')
        PendingCustomerRegistration.objects.filter(email='cmdclean@example.com').update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        out = StringIO()
        call_command('cleanup_pending_registrations', stdout=out)
        self.assertIn('Deleted', out.getvalue())
        self.assertFalse(PendingCustomerRegistration.objects.filter(email='cmdclean@example.com').exists())

    def test_migrate_legacy_unverified_to_pending(self):
        user = User.objects.create_user(
            username='legacy',
            email='legacy@example.com',
            password='StrongPassword123',
            is_active=False,
        )
        CustomerProfile.objects.create(user=user, is_email_verified=False, phone=None)
        pending = migrate_legacy_unverified_to_pending(user)
        self.assertIsNotNone(pending)
        self.assertEqual(pending.email, 'legacy@example.com')
        self.assertFalse(User.objects.filter(email='legacy@example.com').exists())

    def test_password_reset_subject_code_first(self):
        user = User.objects.create_user(
            username='resetsubj',
            email='resetsubj@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(user=user, is_email_verified=True)
        mail.outbox.clear()
        response = self.client.post(
            reverse('user_management:password-reset-request'),
            {'email': user.email},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertRegex(mail.outbox[0].subject, r'^\d{6} is your password reset code$')
