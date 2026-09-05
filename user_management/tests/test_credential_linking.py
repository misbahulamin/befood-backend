"""Credential linking: password setup + phone availability."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from user_management.models import CustomerProfile
from user_management.services.auth_session import issue_auth_session
from user_management.services.customer_factory import create_phone_only_customer


def _make_verified_email_customer(email='customer@example.com', password='TestPass123!'):
    user = User.objects.create_user(
        username=email.split('@')[0] + email.split('@')[1][:3],
        email=email,
        password=password,
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    CustomerProfile.objects.create(
        user=user,
        is_email_verified=True,
        email_verified_at=timezone.now(),
        is_phone_verified=False,
    )
    return user


def _make_social_customer(email='social@example.com'):
    user = _make_verified_email_customer(email=email, password='TempPass123!')
    user.set_unusable_password()
    user.save(update_fields=['password'])
    return user


class PasswordSetupAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_login_password_setup_required(self):
        _make_social_customer('nopw@example.com')
        response = self.client.post(
            '/user_management/login/',
            {'email': 'nopw@example.com', 'password': 'anything'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'password_setup_required')
        self.assertTrue(response.data['password_setup_required'])

    def test_set_password_then_email_login(self):
        user = _make_social_customer('setup@example.com')
        session = issue_auth_session(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {session.key}')
        set_resp = self.client.post(
            '/user_management/set-password/',
            {
                'password': 'NewStrongPass123!',
                'password_confirm': 'NewStrongPass123!',
            },
            format='json',
        )
        self.assertEqual(set_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(set_resp.data['has_password'])
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())

        self.client.credentials()
        login = self.client.post(
            '/user_management/login/',
            {'email': 'setup@example.com', 'password': 'NewStrongPass123!'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn('token', login.data)
        self.assertTrue(login.data['has_password'])

    def test_set_password_requires_auth(self):
        response = self.client.post(
            '/user_management/set-password/',
            {'password': 'NewStrongPass123!', 'password_confirm': 'NewStrongPass123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_requires_current(self):
        user = _make_verified_email_customer('changepw@example.com', password='OldPass123!')
        session = issue_auth_session(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {session.key}')
        bad = self.client.post(
            '/user_management/set-password/',
            {
                'password': 'NewStrongPass123!',
                'password_confirm': 'NewStrongPass123!',
            },
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad.data['code'], 'CURRENT_PASSWORD_REQUIRED')

        ok = self.client.post(
            '/user_management/set-password/',
            {
                'password': 'NewStrongPass123!',
                'password_confirm': 'NewStrongPass123!',
                'current_password': 'OldPass123!',
            },
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)


class PhoneAvailabilityAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/user_management/phone/check-availability/'

    def test_login_context_allows_existing(self):
        create_phone_only_customer('1711111111')
        response = self.client.post(
            self.url,
            {'phone': '01711111111', 'context': 'login'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['phone_exists'])
        self.assertTrue(response.data['available'])
        self.assertTrue(response.data['verification_allowed'])

    def test_bind_context_blocks_taken(self):
        create_phone_only_customer('1722222222')
        user = _make_verified_email_customer('binder@example.com')
        session = issue_auth_session(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {session.key}')
        response = self.client.post(
            self.url,
            {'phone': '01722222222', 'context': 'bind'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['available'])
        self.assertFalse(response.data['verification_allowed'])
        self.assertEqual(response.data['reason'], 'PHONE_ALREADY_REGISTERED')

    def test_bind_context_allows_free(self):
        user = _make_verified_email_customer('freephone@example.com')
        session = issue_auth_session(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {session.key}')
        response = self.client.post(
            self.url,
            {'phone': '01733333333', 'context': 'bind'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])
        self.assertTrue(response.data['verification_allowed'])

    def test_bind_context_requires_auth(self):
        response = self.client.post(
            self.url,
            {'phone': '01744444444', 'context': 'bind'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_anonymous_existing_phone_otp_still_sends(self, mock_send):
        mock_send.return_value = {'error': 0}
        create_phone_only_customer('1755555555')
        response = self.client.post(
            '/user_management/phone/otp/send/',
            {'phone': '01755555555'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once()
