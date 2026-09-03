from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from app_config.models import (
    DEFAULT_APP_VERSION,
    DEFAULT_PLAY_STORE_URL,
    AppVersionSettings,
)
from user_management.models import AdminProfile, CustomerProfile

User = get_user_model()


@override_settings(ROOT_URLCONF='core.urls')
class PublicAppVersionAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('app_config:version')

    def test_anonymous_get_creates_defaults(self):
        AppVersionSettings.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['latest_version'], DEFAULT_APP_VERSION)
        self.assertEqual(
            response.data['minimum_supported_version'], DEFAULT_APP_VERSION
        )
        self.assertEqual(response.data['play_store_url'], DEFAULT_PLAY_STORE_URL)
        self.assertIn('app_store_url', response.data)
        self.assertIn('updated_at', response.data)
        self.assertTrue(AppVersionSettings.objects.filter(pk=1).exists())

    def test_invalid_auth_token_still_returns_200(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid-token-value')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['latest_version'], DEFAULT_APP_VERSION)


@override_settings(ROOT_URLCONF='core.urls')
class AdminAppVersionAPITests(APITestCase):
    def setUp(self):
        self.public_url = reverse('app_config:version')
        self.admin_url = reverse('web_app_config:version')

        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='app_version_admin',
            email='app_version_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(self.admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='app_version_customer',
            email='app_version_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712999901',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_admin_patch_updates_public_get(self):
        self._auth(self.admin_token)
        patched = self.client.patch(
            self.admin_url,
            {
                'latest_version': '1.0.14',
                'minimum_supported_version': '1.0.14',
            },
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['latest_version'], '1.0.14')
        self.assertEqual(patched.data['minimum_supported_version'], '1.0.14')

        self.client.credentials()
        public = self.client.get(self.public_url)
        self.assertEqual(public.status_code, status.HTTP_200_OK)
        self.assertEqual(public.data['latest_version'], '1.0.14')
        self.assertEqual(public.data['minimum_supported_version'], '1.0.14')

    def test_admin_rejects_invalid_semver(self):
        self._auth(self.admin_token)
        before = AppVersionSettings.load()
        response = self.client.patch(
            self.admin_url,
            {'latest_version': '1.0'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        after = AppVersionSettings.load()
        self.assertEqual(after.latest_version, before.latest_version)

    def test_customer_cannot_patch(self):
        self._auth(self.customer_token)
        response = self.client.patch(
            self.admin_url,
            {'latest_version': '9.9.9'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_admin_endpoint_rejected(self):
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
