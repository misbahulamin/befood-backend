from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from user_management.models import CustomerProfile
from user_management.services.email_verification import generate_token as generate_activation_token
from user_management.services.email_verification import mark_email_verified
from user_management.services.password_reset import (
    PASSWORD_RESET_CONFIRM_SUCCESS_MESSAGE,
    PASSWORD_RESET_INVALID_TOKEN_MESSAGE,
    PASSWORD_RESET_REQUEST_MESSAGE,
    PASSWORD_RESET_VALIDATE_SUCCESS_MESSAGE,
    generate_password_reset_token,
    generate_password_reset_uid,
)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://www.befood.com.bd',
    PASSWORD_RESET_FRONTEND_PATH='/reset-password',
)
class CustomerPasswordResetFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.request_url = reverse('user_management:password-reset-request')
        self.validate_url = reverse('user_management:password-reset-validate')
        self.confirm_url = reverse('user_management:password-reset-confirm')
        self.login_url = reverse('user_management:login')

    def _make_customer(
        self,
        *,
        email='customer@example.com',
        password='StrongPassword123',
        verified=True,
    ):
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name='Rahim',
            is_active=verified,
        )
        profile = CustomerProfile.objects.create(user=user)
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        if verified:
            mark_email_verified(profile)
        return user, profile

    def test_request_existing_customer_sends_mail(self):
        self._make_customer(email='reset@example.com')
        response = self.client.post(
            self.request_url,
            {'email': 'reset@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], PASSWORD_RESET_REQUEST_MESSAGE)
        self.assertEqual(len(mail.outbox), 1)

    def test_request_unknown_email_is_anti_enumeration(self):
        response = self.client.post(
            self.request_url,
            {'email': 'missing@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], PASSWORD_RESET_REQUEST_MESSAGE)
        self.assertEqual(len(mail.outbox), 0)

    def test_validate_valid_token(self):
        user, _ = self._make_customer(email='valid@example.com')
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        response = self.client.post(
            self.validate_url,
            {'uid': uid, 'token': token},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], PASSWORD_RESET_VALIDATE_SUCCESS_MESSAGE)

    def test_validate_invalid_token(self):
        user, _ = self._make_customer(email='invalid@example.com')
        uid = generate_password_reset_uid(user)
        response = self.client.post(
            self.validate_url,
            {'uid': uid, 'token': 'not-a-real-token'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_validate_malformed_uid(self):
        response = self.client.post(
            self.validate_url,
            {'uid': '!!!', 'token': 'anything'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_validate_rejects_activation_token(self):
        user, _ = self._make_customer(email='activation@example.com')
        uid = generate_password_reset_uid(user)
        activation_token = generate_activation_token(user)
        response = self.client.post(
            self.validate_url,
            {'uid': uid, 'token': activation_token},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_confirm_success_sets_password_and_returns_message(self):
        user, _ = self._make_customer(email='confirm@example.com', password='OldStrongPass123')
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        response = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': token,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], PASSWORD_RESET_CONFIRM_SUCCESS_MESSAGE)
        self.assertNotIn('token', response.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewStrongPassword123'))
        self.assertFalse(user.check_password('OldStrongPass123'))

    def test_confirm_password_mismatch(self):
        user, _ = self._make_customer(email='mismatch@example.com')
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        response = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': token,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'DifferentPassword123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('confirm_password', response.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password('StrongPassword123'))

    def test_confirm_weak_password(self):
        user, _ = self._make_customer(email='weak@example.com')
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        response = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': token,
                'new_password': '123',
                'confirm_password': '123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('new_password', response.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password('StrongPassword123'))

    def test_confirm_invalid_token(self):
        user, _ = self._make_customer(email='badtoken@example.com')
        uid = generate_password_reset_uid(user)
        response = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': 'bad-token',
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_confirm_rejects_activation_token(self):
        user, _ = self._make_customer(email='actconfirm@example.com')
        uid = generate_password_reset_uid(user)
        activation_token = generate_activation_token(user)
        response = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': activation_token,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_confirm_token_cannot_be_reused(self):
        user, _ = self._make_customer(email='reuse@example.com')
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        payload = {
            'uid': uid,
            'token': token,
            'new_password': 'NewStrongPassword123',
            'confirm_password': 'NewStrongPassword123',
        }
        first = self.client.post(self.confirm_url, payload, format='json')
        self.assertEqual(first.status_code, 200)
        second = self.client.post(self.confirm_url, payload, format='json')
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.data['detail'], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_confirm_deletes_existing_drf_token(self):
        user, _ = self._make_customer(email='session@example.com')
        old_token = Token.objects.create(user=user)
        uid = generate_password_reset_uid(user)
        reset_token = generate_password_reset_token(user)
        response = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': reset_token,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Token.objects.filter(key=old_token.key).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {old_token.key}')
        me_response = self.client.get(reverse('user_management:me'))
        self.assertEqual(me_response.status_code, 401)

    def test_login_with_new_password_after_confirm(self):
        user, _ = self._make_customer(
            email='loginnew@example.com',
            password='OldStrongPass123',
        )
        uid = generate_password_reset_uid(user)
        token = generate_password_reset_token(user)
        confirm = self.client.post(
            self.confirm_url,
            {
                'uid': uid,
                'token': token,
                'new_password': 'NewStrongPassword123',
                'confirm_password': 'NewStrongPassword123',
            },
            format='json',
        )
        self.assertEqual(confirm.status_code, 200)

        old_login = self.client.post(
            self.login_url,
            {'email': 'loginnew@example.com', 'password': 'OldStrongPass123'},
            format='json',
        )
        self.assertEqual(old_login.status_code, 400)

        new_login = self.client.post(
            self.login_url,
            {'email': 'loginnew@example.com', 'password': 'NewStrongPassword123'},
            format='json',
        )
        self.assertEqual(new_login.status_code, 200)
        self.assertIn('token', new_login.data)
