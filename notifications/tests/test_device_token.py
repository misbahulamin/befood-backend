from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from notifications.services.device_service import (
    get_all_active_device_tokens,
    get_user_device_tokens,
    register_device_token,
)
from user_management.models import DeviceToken


class DeviceTokenAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('notifications:device-token-register')
        self.remove_url = reverse('notifications:device-token-remove')
        self.user = User.objects.create_user(
            username='customer1',
            email='customer1@example.com',
            password='StrongPassword123',
        )
        self.other_user = User.objects.create_user(
            username='customer2',
            email='customer2@example.com',
            password='StrongPassword123',
        )
        self.token_key = Token.objects.create(user=self.user).key
        self.other_token_key = Token.objects.create(user=self.other_user).key
        self.sample_token = 'a' * 140

    def _auth(self, token_key=None):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token_key or self.token_key}')

    def _register_payload(self, **overrides):
        payload = {
            'token': self.sample_token,
            'platform': 'android',
            'device_name': 'Pixel 8',
            'app_version': '1.0.0',
        }
        payload.update(overrides)
        return payload

    def test_unauthenticated_register_returns_401(self):
        response = self.client.post(self.register_url, self._register_payload(), format='json')
        self.assertEqual(response.status_code, 401)

    def test_authenticated_register_creates_device(self):
        self._auth()
        response = self.client.post(self.register_url, self._register_payload(), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['success'], True)
        self.assertEqual(DeviceToken.objects.filter(user=self.user, token=self.sample_token).count(), 1)

    def test_same_user_reregister_updates_without_duplicate(self):
        self._auth()
        self.client.post(self.register_url, self._register_payload(), format='json')
        device = DeviceToken.objects.get(token=self.sample_token)
        device.is_active = False
        device.last_used_at = timezone.now()
        device.save(update_fields=['is_active', 'last_used_at'])
        previous_last_used = device.last_used_at

        response = self.client.post(
            self.register_url,
            self._register_payload(app_version='1.0.1'),
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeviceToken.objects.filter(token=self.sample_token).count(), 1)
        device.refresh_from_db()
        self.assertTrue(device.is_active)
        self.assertEqual(device.app_version, '1.0.1')
        self.assertGreater(device.last_used_at, previous_last_used)

    def test_token_ownership_transfers_to_current_user(self):
        DeviceToken.objects.create(
            user=self.other_user,
            token=self.sample_token,
            platform='ios',
            is_active=True,
        )
        self._auth()
        response = self.client.post(self.register_url, self._register_payload(platform='android'), format='json')
        self.assertEqual(response.status_code, 200)
        device = DeviceToken.objects.get(token=self.sample_token)
        self.assertEqual(device.user_id, self.user.id)
        self.assertEqual(device.platform, 'android')

    def test_invalid_platform_returns_400(self):
        self._auth()
        response = self.client.post(
            self.register_url,
            self._register_payload(platform='windows'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('platform', response.data)

    def test_empty_token_returns_400(self):
        self._auth()
        response = self.client.post(self.register_url, self._register_payload(token='   '), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('token', response.data)

    def test_oversized_optional_fields_return_400(self):
        self._auth()
        response = self.client.post(
            self.register_url,
            self._register_payload(device_name='x' * 101),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('device_name', response.data)

    def test_remove_own_token_deactivates_without_delete(self):
        register_device_token(self.user, self.sample_token, 'android')
        self._auth()
        response = self.client.post(self.remove_url, {'token': self.sample_token}, format='json')
        self.assertEqual(response.status_code, 200)
        device = DeviceToken.objects.get(token=self.sample_token)
        self.assertFalse(device.is_active)

    def test_remove_other_users_token_returns_404(self):
        register_device_token(self.other_user, self.sample_token, 'android')
        self._auth()
        response = self.client.post(self.remove_url, {'token': self.sample_token}, format='json')
        self.assertEqual(response.status_code, 404)
        device = DeviceToken.objects.get(token=self.sample_token)
        self.assertTrue(device.is_active)

    def test_remove_already_inactive_token_is_idempotent(self):
        device = register_device_token(self.user, self.sample_token, 'android')
        device.is_active = False
        device.save(update_fields=['is_active'])
        self._auth()
        response = self.client.post(self.remove_url, {'token': self.sample_token}, format='json')
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertFalse(device.is_active)

    def test_remove_unknown_token_returns_404(self):
        self._auth()
        response = self.client.post(self.remove_url, {'token': 'b' * 140}, format='json')
        self.assertEqual(response.status_code, 404)


class DeviceTokenQueryServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='query-user',
            email='query@example.com',
            password='StrongPassword123',
        )

    def test_get_user_device_tokens_returns_only_active_non_empty(self):
        register_device_token(self.user, 'a' * 140, 'android')
        inactive = register_device_token(self.user, 'b' * 140, 'android')
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])
        DeviceToken.objects.create(user=self.user, token='', platform='android', is_active=True)

        tokens = get_user_device_tokens(self.user)
        self.assertEqual(tokens, ['a' * 140])

    def test_get_all_active_device_tokens_excludes_inactive(self):
        register_device_token(self.user, 'c' * 140, 'android')
        inactive = register_device_token(self.user, 'd' * 140, 'ios')
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])

        tokens = list(get_all_active_device_tokens())
        self.assertEqual(tokens, ['c' * 140])

    def test_get_all_active_device_tokens_uses_values_list_query(self):
        register_device_token(self.user, 'e' * 140, 'android')
        with self.assertNumQueries(1):
            list(get_all_active_device_tokens())


class DeviceTokenOpenAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_urls_registered(self):
        self.assertEqual(reverse('notifications:device-token-register'), '/notifications/device-token/')
        self.assertEqual(reverse('notifications:device-token-remove'), '/notifications/device-token/remove/')

    def test_schema_includes_device_token_endpoints(self):
        response = self.client.get(
            '/api/schema/',
            HTTP_ACCEPT='application/vnd.oai.openapi+json',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('/notifications/device-token/', content)
        self.assertIn('/notifications/device-token/remove/', content)
        self.assertIn('Notifications', content)
