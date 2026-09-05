"""Multi-provider auth: phone OTP, social linking, sessions, unified response."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from notifications.services.device_service import register_device_token
from user_management.models import AuthSession, CustomerProfile, DeviceToken, PhoneAuthOTP, SocialIdentity
from user_management.services.auth_otp import hash_otp_code
from user_management.services.auth_session import issue_auth_session
from user_management.services.customer_factory import create_phone_only_customer
from user_management.services.social_linking import resolve_or_create_social_user


UNIFIED_KEYS = {
    'token',
    'user',
    'customer_profile',
    'device_token_status',
    'auth_provider',
    'groups',
    'phone_verification_required',
    'verification_status',
    'onboarding_completion',
    'location_confirmation',
}


def _make_verified_email_customer(email='customer@example.com', password='TestPass123!'):
    user = User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password=password,
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    CustomerProfile.objects.create(
        user=user,
        is_email_verified=True,
        email_verified_at=timezone.now(),
    )
    return user


class PhoneOtpAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_send_otp_success(self, mock_send):
        mock_send.return_value = {'error': 0}
        response = self.client.post(
            '/user_management/phone/otp/send/',
            {'phone': '+8801712345678'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone'], '1712345678')
        self.assertTrue(PhoneAuthOTP.objects.filter(phone='1712345678').exists())
        mock_send.assert_called_once()

    def test_send_otp_invalid_phone(self):
        response = self.client.post(
            '/user_management/phone/otp/send/',
            {'phone': '123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_phone_format_variants_same_key(self, mock_send):
        mock_send.return_value = {'error': 0}
        for phone in ('01712345678', '+8801712345678', '8801712345678'):
            PhoneAuthOTP.objects.all().delete()
            response = self.client.post(
                '/user_management/phone/otp/send/',
                {'phone': phone},
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['phone'], '1712345678')

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_verify_creates_phone_only_user(self, mock_send):
        mock_send.return_value = {'error': 0}
        self.client.post('/user_management/phone/otp/send/', {'phone': '01712345678'}, format='json')
        otp = PhoneAuthOTP.objects.get(phone='1712345678')
        # Replace hash with known code
        otp.code_hash = hash_otp_code('123456')
        otp.save(update_fields=['code_hash'])

        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '01712345678', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(UNIFIED_KEYS.issubset(response.data.keys()))
        self.assertEqual(response.data['auth_provider'], 'phone')
        self.assertFalse(response.data['phone_verification_required'])
        vs = response.data['verification_status']
        self.assertTrue(vs['phone_verified'])
        self.assertTrue(vs['identity_verified'])
        self.assertFalse(vs['email_verified'])
        self.assertEqual(response.data['user']['email'], '')
        user = User.objects.get(id=response.data['user']['id'])
        self.assertFalse(user.has_usable_password())
        profile = user.customer_profile
        self.assertTrue(profile.is_phone_verified)
        self.assertEqual(profile.phone, '1712345678')
        self.assertFalse(profile.profile_completed)

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_verify_existing_user(self, mock_send):
        mock_send.return_value = {'error': 0}
        user, profile = create_phone_only_customer('1712345678')
        self.client.post('/user_management/phone/otp/send/', {'phone': '01712345678'}, format='json')
        otp = PhoneAuthOTP.objects.filter(phone='1712345678').latest('created_at')
        otp.code_hash = hash_otp_code('654321')
        otp.save(update_fields=['code_hash'])

        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '+8801712345678', 'otp': '654321'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['id'], user.id)

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_wrong_otp(self, mock_send):
        mock_send.return_value = {'error': 0}
        self.client.post('/user_management/phone/otp/send/', {'phone': '01712345678'}, format='json')
        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '01712345678', 'otp': '000000'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        SMS_NET_BD_API_KEY='test-key',
        SMS_NET_BD_SEND_SMS_URL='https://sms.test/send',
        PHONE_OTP_RESEND_COOLDOWN_SECONDS=3600,
    )
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_resend_cooldown(self, mock_send):
        mock_send.return_value = {'error': 0}
        first = self.client.post(
            '/user_management/phone/otp/send/', {'phone': '01712345678'}, format='json'
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.client.post(
            '/user_management/phone/otp/send/', {'phone': '01712345678'}, format='json'
        )
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class SocialLinkingTests(TestCase):
    def test_link_by_verified_email(self):
        user = _make_verified_email_customer('LinkMe@Example.com')
        resolved, identity, created = resolve_or_create_social_user(
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id='google-sub-1',
            email='linkme@example.com',
            email_verified=True,
        )
        self.assertFalse(created)
        self.assertEqual(resolved.id, user.id)
        self.assertEqual(identity.provider, 'google')

    def test_create_password_less_social_user(self):
        user, identity, created = resolve_or_create_social_user(
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id='google-sub-new',
            email='new@example.com',
            email_verified=True,
            first_name='New',
        )
        self.assertTrue(created)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.customer_profile.is_email_verified)

    def test_conflict_provider_id(self):
        user_a = _make_verified_email_customer('a@example.com')
        SocialIdentity.objects.create(
            user=user_a,
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id='shared-sub',
        )
        user_b = _make_verified_email_customer('b@example.com')
        # Existing identity should return user A, not raise — conflict is when binding to different user
        resolved, _, created = resolve_or_create_social_user(
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id='shared-sub',
            email='b@example.com',
            email_verified=True,
        )
        self.assertEqual(resolved.id, user_a.id)
        self.assertFalse(created)

    def test_link_by_verified_phone(self):
        user, _ = create_phone_only_customer('1712345678')
        resolved, identity, created = resolve_or_create_social_user(
            provider=SocialIdentity.Provider.FACEBOOK,
            provider_user_id='fb-1',
            phone='+8801712345678',
            phone_verified=True,
        )
        self.assertFalse(created)
        self.assertEqual(resolved.id, user.id)
        self.assertEqual(identity.provider, 'facebook')


class GoogleFacebookAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(GOOGLE_WEB_CLIENT_ID='web-client')
    @patch('user_management.services.google_oauth.verify_google_id_token')
    def test_google_login_new_user(self, mock_verify):
        mock_verify.return_value = {
            'sub': 'g-sub-1',
            'email': 'googleuser@example.com',
            'email_verified': True,
            'given_name': 'G',
            'family_name': 'U',
        }
        response = self.client.post(
            '/user_management/oauth/google/',
            {'id_token': 'fake-token'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(UNIFIED_KEYS.issubset(response.data.keys()))
        self.assertEqual(response.data['auth_provider'], 'google')
        self.assertTrue(response.data['phone_verification_required'])
        vs = response.data['verification_status']
        self.assertTrue(vs['google_verified'])
        self.assertTrue(vs['identity_verified'])
        self.assertTrue(vs['email_verified'])  # Google asserted email_verified claim
        user = User.objects.get(id=response.data['user']['id'])
        self.assertFalse(user.has_usable_password())

    @override_settings(GOOGLE_WEB_CLIENT_ID='web-client')
    @patch('user_management.services.google_oauth.verify_google_id_token')
    def test_google_existing_with_verified_phone(self, mock_verify):
        user, profile = create_phone_only_customer('1711111111')
        SocialIdentity.objects.create(
            user=user,
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id='g-sub-existing',
        )
        mock_verify.return_value = {
            'sub': 'g-sub-existing',
            'email': '',
            'email_verified': False,
            'given_name': '',
            'family_name': '',
        }
        response = self.client.post(
            '/user_management/oauth/google/',
            {'id_token': 'fake-token'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['phone_verification_required'])
        self.assertEqual(response.data['user']['id'], user.id)

    @override_settings(GOOGLE_WEB_CLIENT_ID='web-client')
    @patch('user_management.services.google_oauth.verify_google_id_token')
    def test_google_invalid_token(self, mock_verify):
        from user_management.services.google_oauth import GoogleOAuthError

        mock_verify.side_effect = GoogleOAuthError('Invalid Google ID token.', code='INVALID_TOKEN')
        response = self.client.post(
            '/user_management/oauth/google/',
            {'id_token': 'bad'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(FACEBOOK_APP_ID='app', FACEBOOK_APP_SECRET='secret')
    @patch('user_management.services.facebook_oauth.verify_facebook_access_token')
    def test_facebook_login(self, mock_verify):
        mock_verify.return_value = {
            'id': 'fb-99',
            'email': 'fb@example.com',
            'email_verified': True,
            'first_name': 'F',
            'last_name': 'B',
        }
        response = self.client.post(
            '/user_management/oauth/facebook/',
            {'access_token': 'fake'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['auth_provider'], 'facebook')
        self.assertTrue(response.data['phone_verification_required'])
        vs = response.data['verification_status']
        self.assertTrue(vs['facebook_verified'])
        self.assertTrue(vs['identity_verified'])
        # Email present on Facebook profile must not imply email ownership.
        self.assertFalse(vs['email_verified'])
        user = User.objects.get(id=response.data['user']['id'])
        self.assertFalse(user.customer_profile.is_email_verified)


class SessionLogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _make_verified_email_customer()
        self.session_a = issue_auth_session(self.user, platform='android')
        self.session_b = issue_auth_session(self.user, platform='ios')
        register_device_token(self.user, 'a' * 140, 'android')
        register_device_token(self.user, 'b' * 140, 'ios')

    def test_logout_current_keeps_other_session(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session_a.key}')
        response = self.client.post(
            '/user_management/logout/',
            {'device_token': 'a' * 140},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.session_a.refresh_from_db()
        self.session_b.refresh_from_db()
        self.assertIsNotNone(self.session_a.revoked_at)
        self.assertIsNone(self.session_b.revoked_at)

        # Device A unauthorized; device B still works
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session_a.key}')
        self.assertEqual(self.client.get('/user_management/me/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session_b.key}')
        self.assertEqual(self.client.get('/user_management/me/').status_code, status.HTTP_200_OK)

        self.assertFalse(DeviceToken.objects.get(token='a' * 140).is_active)
        self.assertTrue(DeviceToken.objects.get(token='b' * 140).is_active)

    def test_logout_all(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session_a.key}')
        response = self.client.post('/user_management/logout-all/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.session_a.refresh_from_db()
        self.session_b.refresh_from_db()
        self.assertIsNotNone(self.session_a.revoked_at)
        self.assertIsNotNone(self.session_b.revoked_at)
        self.assertEqual(DeviceToken.objects.filter(user=self.user, is_active=True).count(), 0)

    def test_unified_email_login_envelope(self):
        response = self.client.post(
            '/user_management/login/',
            {'email': 'customer@example.com', 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(UNIFIED_KEYS.issubset(response.data.keys()))
        self.assertEqual(response.data['auth_provider'], 'email')
        vs = response.data['verification_status']
        self.assertTrue(vs['email_verified'])
        self.assertTrue(vs['identity_verified'])

    def test_email_case_normalization_login(self):
        response = self.client.post(
            '/user_management/login/',
            {'email': 'Customer@Example.com', 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get('/user_management/me/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session_a.key}')
        self.assertEqual(self.client.get('/user_management/me/').status_code, status.HTTP_200_OK)

    def test_multi_device_sessions_active(self):
        self.assertEqual(
            AuthSession.objects.filter(user=self.user, revoked_at__isnull=True).count(),
            2,
        )
        self.assertEqual(DeviceToken.objects.filter(user=self.user, is_active=True).count(), 2)
