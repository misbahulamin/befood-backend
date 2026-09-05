"""Unified customer auth flow: email-check, phone gate, authenticated phone bind."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from user_management.models import CustomerProfile, PhoneAuthOTP, SocialIdentity
from user_management.services.auth_otp import hash_otp_code
from user_management.services.auth_session import issue_auth_session
from user_management.services.customer_factory import create_phone_only_customer
from user_management.services.pending_registration import issue_pending_otp
from user_management.models import PendingCustomerRegistration


def _make_verified_email_customer(email='customer@example.com', password='TestPass123!', phone=None):
    user = User.objects.create_user(
        username=email.split('@')[0] + email.split('@')[1][:3],
        email=email,
        password=password,
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    CustomerProfile.objects.create(
        user=user,
        phone=phone,
        is_email_verified=True,
        email_verified_at=timezone.now(),
        is_phone_verified=False,
    )
    return user


class EmailCheckAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/user_management/customer/email-check/'

    def test_exists(self):
        _make_verified_email_customer('exists@example.com')
        response = self.client.post(self.url, {'email': 'Exists@Example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'exists')
        self.assertEqual(response.data['email'], 'exists@example.com')
        self.assertTrue(response.data['has_password'])
        self.assertFalse(response.data['password_setup_required'])

    def test_exists_social_without_password(self):
        user = _make_verified_email_customer('social@example.com', password='TempPass123!')
        user.set_unusable_password()
        user.save(update_fields=['password'])
        response = self.client.post(self.url, {'email': 'social@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'exists')
        self.assertFalse(response.data['has_password'])
        self.assertTrue(response.data['password_setup_required'])

    def test_pending(self):
        self.client.post(
            '/user_management/customer/register/',
            {'email': 'pending@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertTrue(
            PendingCustomerRegistration.objects.filter(email='pending@example.com').exists()
        )
        response = self.client.post(self.url, {'email': 'pending@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending')
        self.assertNotIn('has_password', response.data)
        self.assertNotIn('password_setup_required', response.data)

    def test_available(self):
        response = self.client.post(self.url, {'email': 'fresh@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'available')
        self.assertNotIn('has_password', response.data)
        self.assertNotIn('password_setup_required', response.data)

    def test_invalid_email(self):
        response = self.client.post(self.url, {'email': 'not-an-email'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PhoneVerificationGateTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_email_login_without_phone_sets_flag(self):
        user = _make_verified_email_customer('nophone@example.com', password='StrongPassword123')
        response = self.client.post(
            '/user_management/login/',
            {'email': 'nophone@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertTrue(response.data['phone_verification_required'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {response.data["token"]}')
        me = self.client.get('/user_management/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertTrue(me.data['phone_verification_required'])

    def test_email_verify_includes_phone_flag(self):
        self.client.post(
            '/user_management/customer/register/',
            {'email': 'verifyflag@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        pending = PendingCustomerRegistration.objects.get(email='verifyflag@example.com')
        otp = issue_pending_otp(pending, force_new=True).plaintext_otp
        response = self.client.post(
            '/user_management/verify-email/otp/',
            {'email': 'verifyflag@example.com', 'otp': otp},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertTrue(response.data['phone_verification_required'])
        self.assertTrue(response.data['email_verified'])


class PhoneBindAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _make_verified_email_customer('bindme@example.com')
        self.session = issue_auth_session(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session.key}')

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_bind_attaches_phone_without_second_user(self, mock_send):
        mock_send.return_value = {'error': 0}
        user_count_before = User.objects.count()
        send = self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01712345678'},
            format='json',
        )
        self.assertEqual(send.status_code, status.HTTP_200_OK)
        otp = PhoneAuthOTP.objects.filter(phone='1712345678').latest('created_at')
        otp.code_hash = hash_otp_code('123456')
        otp.save(update_fields=['code_hash'])

        response = self.client.post(
            '/user_management/phone/otp/bind/verify/',
            {'phone': '01712345678', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['phone_verification_required'])
        self.assertEqual(User.objects.count(), user_count_before)
        self.user.customer_profile.refresh_from_db()
        self.assertEqual(self.user.customer_profile.phone, '1712345678')
        self.assertTrue(self.user.customer_profile.is_phone_verified)

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_bind_conflict_when_phone_owned(self, mock_send):
        mock_send.return_value = {'error': 0}
        create_phone_only_customer('1799999999')
        send = self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01799999999'},
            format='json',
        )
        self.assertEqual(send.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(send.data['code'], 'PHONE_CONFLICT')
        mock_send.assert_not_called()
        self.assertFalse(PhoneAuthOTP.objects.filter(phone='1799999999').exists())

    def test_bind_requires_auth(self):
        self.client.credentials()
        response = self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01712345678'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SocialPhoneBindFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(
        GOOGLE_WEB_CLIENT_ID='web-client',
        SMS_NET_BD_API_KEY='test-key',
        SMS_NET_BD_SEND_SMS_URL='https://sms.test/send',
    )
    @patch('user_management.services.phone_otp.send_otp_sms')
    @patch('user_management.services.google_oauth.verify_google_id_token')
    def test_google_new_then_bind_phone(self, mock_verify, mock_send):
        mock_send.return_value = {'error': 0}
        mock_verify.return_value = {
            'sub': 'g-bind-1',
            'email': 'gsocial@example.com',
            'email_verified': True,
            'given_name': 'G',
            'family_name': 'S',
        }
        login = self.client.post(
            '/user_management/oauth/google/',
            {'id_token': 'fake'},
            format='json',
        )
        self.assertTrue(login.data['phone_verification_required'])
        token = login.data['token']
        user_id = login.data['user']['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01715555555'},
            format='json',
        )
        otp = PhoneAuthOTP.objects.filter(phone='1715555555').latest('created_at')
        otp.code_hash = hash_otp_code('222222')
        otp.save(update_fields=['code_hash'])

        bind = self.client.post(
            '/user_management/phone/otp/bind/verify/',
            {'phone': '01715555555', 'otp': '222222'},
            format='json',
        )
        self.assertEqual(bind.status_code, status.HTTP_200_OK)
        self.assertFalse(bind.data['phone_verification_required'])
        self.assertEqual(bind.data['user']['id'], user_id)
        self.assertEqual(User.objects.filter(id=user_id).count(), 1)
        self.assertTrue(
            SocialIdentity.objects.filter(
                user_id=user_id, provider=SocialIdentity.Provider.GOOGLE
            ).exists()
        )
