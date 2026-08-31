from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from user_management.models import CustomerAuthOTP, CustomerProfile
from user_management.services.auth_otp import (
    PURPOSE_EMAIL_VERIFICATION,
    PURPOSE_PASSWORD_RESET,
    IssueStatus,
    hash_otp_code,
    issue_otp,
)
from user_management.services.email_verification import (
    generate_token,
    generate_uid,
    mark_email_verified,
)
from user_management.services.password_reset import (
    generate_password_reset_token,
    generate_password_reset_uid,
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
class CustomerAuthOTPTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.register_url = reverse('user_management:customer-register')
        self.login_url = reverse('user_management:login')
        self.verify_otp_url = reverse('user_management:verify-email-otp')
        self.resend_url = reverse('user_management:resend-verification')
        self.resend_otp_alias = reverse('user_management:verify-email-resend-otp')
        self.reset_request = reverse('user_management:password-reset-request')
        self.reset_request_otp = reverse('user_management:password-reset-request-otp')
        self.reset_validate_otp = reverse('user_management:password-reset-validate-otp')
        self.reset_confirm_otp = reverse('user_management:password-reset-confirm-otp')
        self.reset_validate = reverse('user_management:password-reset-validate')
        self.reset_confirm = reverse('user_management:password-reset-confirm')

    def create_unverified_customer(self, email='otpuser@example.com', password='StrongPassword123'):
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            is_active=False,
        )
        CustomerProfile.objects.create(user=user, is_email_verified=False)
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        return user

    def create_verified_customer(self, email='verified@example.com', password='StrongPassword123'):
        user = self.create_unverified_customer(email=email, password=password)
        mark_email_verified(user.customer_profile)
        return user

    def plaintext_from_issue(self, user, purpose):
        result = issue_otp(user, purpose)
        self.assertEqual(result.status, IssueStatus.ISSUED)
        self.assertIsNotNone(result.plaintext_otp)
        self.assertFalse(
            CustomerAuthOTP.objects.filter(code_hash=result.plaintext_otp).exists()
        )
        self.assertTrue(
            CustomerAuthOTP.objects.filter(
                user=user,
                purpose=purpose,
                code_hash=hash_otp_code(result.plaintext_otp),
            ).exists()
        )
        return result.plaintext_otp

    def test_issue_and_verify_email_otp(self):
        user = self.create_unverified_customer()
        otp = self.plaintext_from_issue(user, PURPOSE_EMAIL_VERIFICATION)
        response = self.client.post(
            self.verify_otp_url,
            {'email': user.email, 'otp': otp},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        user.customer_profile.refresh_from_db()
        self.assertTrue(user.customer_profile.is_email_verified)

    def test_reject_wrong_otp(self):
        user = self.create_unverified_customer()
        self.plaintext_from_issue(user, PURPOSE_EMAIL_VERIFICATION)
        response = self.client.post(
            self.verify_otp_url,
            {'email': user.email, 'otp': '000000'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid', response.data['detail'])

    def test_reject_expired_otp(self):
        user = self.create_unverified_customer()
        otp = self.plaintext_from_issue(user, PURPOSE_EMAIL_VERIFICATION)
        CustomerAuthOTP.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        response = self.client.post(
            self.verify_otp_url,
            {'email': user.email, 'otp': otp},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'OTP expired.')

    def test_resend_within_cooldown_does_not_reissue(self):
        user = self.create_unverified_customer()
        first = issue_otp(user, PURPOSE_EMAIL_VERIFICATION)
        self.assertEqual(first.status, IssueStatus.ISSUED)
        second = issue_otp(user, PURPOSE_EMAIL_VERIFICATION)
        self.assertEqual(second.status, IssueStatus.REUSED)
        self.assertEqual(
            CustomerAuthOTP.objects.filter(user=user, purpose=PURPOSE_EMAIL_VERIFICATION).count(),
            1,
        )

    def test_hourly_cap_enforced(self):
        user = self.create_unverified_customer()
        with override_settings(AUTH_OTP_MAX_ISSUES_PER_HOUR=2, AUTH_OTP_RESEND_COOLDOWN_SECONDS=0):
            self.assertEqual(issue_otp(user, PURPOSE_EMAIL_VERIFICATION).status, IssueStatus.ISSUED)
            self.assertEqual(issue_otp(user, PURPOSE_EMAIL_VERIFICATION).status, IssueStatus.ISSUED)
            self.assertEqual(
                issue_otp(user, PURPOSE_EMAIL_VERIFICATION).status,
                IssueStatus.RATE_LIMITED,
            )

    def test_password_reset_otp_validate_does_not_consume(self):
        user = self.create_verified_customer(email='resetotp@example.com')
        otp = self.plaintext_from_issue(user, PURPOSE_PASSWORD_RESET)
        response = self.client.post(
            self.reset_validate_otp,
            {'email': user.email, 'otp': otp},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        row = CustomerAuthOTP.objects.get(user=user, purpose=PURPOSE_PASSWORD_RESET)
        self.assertIsNone(row.consumed_at)

    def test_confirm_otp_without_prior_validate(self):
        user = self.create_verified_customer(email='confirmotp@example.com')
        Token.objects.create(user=user)
        otp = self.plaintext_from_issue(user, PURPOSE_PASSWORD_RESET)
        response = self.client.post(
            self.reset_confirm_otp,
            {
                'email': user.email,
                'otp': otp,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewStrongPassword123'))
        self.assertFalse(Token.objects.filter(user=user).exists())
        row = CustomerAuthOTP.objects.get(user=user, purpose=PURPOSE_PASSWORD_RESET)
        self.assertIsNotNone(row.consumed_at)

    def test_reject_reused_password_reset_otp(self):
        user = self.create_verified_customer(email='reuseotp@example.com')
        otp = self.plaintext_from_issue(user, PURPOSE_PASSWORD_RESET)
        first = self.client.post(
            self.reset_confirm_otp,
            {
                'email': user.email,
                'otp': otp,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            self.reset_confirm_otp,
            {
                'email': user.email,
                'otp': otp,
                'new_password': 'AnotherStrongPass123',
                'confirm_password': 'AnotherStrongPass123',
            },
            format='json',
        )
        self.assertEqual(second.status_code, 400)

    def test_unverified_login_sends_then_reuses_within_cooldown(self):
        user = self.create_unverified_customer(email='autologin@example.com')
        mail.outbox.clear()
        first = self.client.post(
            self.login_url,
            {'email': user.email, 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(first.status_code, 400)
        self.assertEqual(first.data['code'], 'email_not_verified')
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertRegex(body, r'\b\d{6}\b')
        self.assertIn('/verify-email/', body)

        second = self.client.post(
            self.login_url,
            {'email': user.email, 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.data['code'], 'email_not_verified')
        self.assertEqual(len(mail.outbox), 1)

    def test_wrong_password_does_not_send_verification_email(self):
        user = self.create_unverified_customer(email='wrongpass@example.com')
        mail.outbox.clear()
        response = self.client.post(
            self.login_url,
            {'email': user.email, 'password': 'WrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Invalid credentials.')
        self.assertEqual(len(mail.outbox), 0)

    def test_link_email_verification_still_works(self):
        user = self.create_unverified_customer(email='linkverify@example.com')
        uid = generate_uid(user)
        token = generate_token(user)
        response = self.client.get(
            reverse('user_management:verify-email', kwargs={'uidb64': uid, 'token': token})
        )
        self.assertEqual(response.status_code, 200)
        user.customer_profile.refresh_from_db()
        self.assertTrue(user.customer_profile.is_email_verified)

    def test_link_password_reset_still_works(self):
        user = self.create_verified_customer(email='linkreset@example.com')
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        confirm = self.client.post(
            self.reset_confirm,
            {
                'uid': uid,
                'token': token,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(confirm.status_code, 200)

    def test_purpose_isolation(self):
        user = self.create_unverified_customer(email='isolate@example.com')
        reset_otp = self.plaintext_from_issue(user, PURPOSE_PASSWORD_RESET)
        response = self.client.post(
            self.verify_otp_url,
            {'email': user.email, 'otp': reset_otp},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_registration_email_includes_otp_and_link(self):
        mail.outbox.clear()
        response = self.client.post(
            self.register_url,
            {'email': 'regotp@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        html = mail.outbox[0].alternatives[0][0]
        self.assertRegex(body, r'\b\d{6}\b')
        self.assertIn('/verify-email/', body)
        self.assertRegex(html, r'\d{6}')
        user = User.objects.get(email='regotp@example.com')
        row = CustomerAuthOTP.objects.get(user=user, purpose=PURPOSE_EMAIL_VERIFICATION)
        self.assertNotRegex(row.code_hash, r'^\d{6}$')

    def test_password_reset_request_email_includes_otp_and_link(self):
        user = self.create_verified_customer(email='resetmail@example.com')
        mail.outbox.clear()
        response = self.client.post(
            self.reset_request_otp,
            {'email': user.email},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertRegex(body, r'\b\d{6}\b')
        self.assertIn('/reset-password', body)

    def test_resend_alias_works(self):
        user = self.create_unverified_customer(email='resendalias@example.com')
        mail.outbox.clear()
        response = self.client.post(
            self.resend_otp_alias,
            {'email': user.email},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
