from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from user_management.models import AdminProfile, CustomerProfile


class AdminAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_login_url = reverse('user_management:admin-login')
        self.admin_me_url = reverse('user_management:admin-me')
        self.customer_login_url = reverse('user_management:login')
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')

    def create_admin_user(self, email='admin@example.com', password='StrongPassword123', is_verified=True):
        user = User.objects.create_user(
            username='admin-user',
            email=email,
            password=password,
            first_name='Admin',
            last_name='User',
            is_active=is_verified,
        )
        AdminProfile.objects.create(user=user, is_verified=is_verified)
        user.groups.add(self.admin_group)
        return user

    def create_customer_user(self, email='customer@example.com', password='StrongPassword123'):
        user = User.objects.create_user(
            username='customer-user',
            email=email,
            password=password,
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=user,
            phone='1712345678',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        user.groups.add(customer_group)
        return user

    def test_verified_admin_can_login(self):
        self.create_admin_user()
        response = self.client.post(
            self.admin_login_url,
            {'email': 'admin@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertTrue(response.data['is_admin'])
        self.assertEqual(response.data['admin_profile']['is_verified'], True)

    def test_unverified_admin_cannot_login(self):
        self.create_admin_user(is_verified=False)
        response = self.client.post(
            self.admin_login_url,
            {'email': 'admin@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Admin account is not verified yet.')

    def test_customer_cannot_use_admin_login(self):
        self.create_customer_user()
        response = self.client.post(
            self.admin_login_url,
            {'email': 'customer@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'This account is not authorized for admin login.')

    def test_superuser_can_login_via_admin_endpoint(self):
        User.objects.create_superuser(
            username='super-admin',
            email='super@example.com',
            password='StrongPassword123',
        )
        response = self.client.post(
            self.admin_login_url,
            {'email': 'super@example.com', 'password': 'StrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['user']['is_superuser'])

    def test_admin_me_returns_current_admin(self):
        user = self.create_admin_user()
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(self.admin_me_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_admin'])
        self.assertEqual(response.data['user']['email'], 'admin@example.com')

    def test_customer_cannot_access_admin_me(self):
        user = self.create_customer_user()
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(self.admin_me_url)
        self.assertEqual(response.status_code, 403)

    def test_invalid_admin_credentials_are_rejected(self):
        self.create_admin_user()
        response = self.client.post(
            self.admin_login_url,
            {'email': 'admin@example.com', 'password': 'WrongPassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Invalid credentials.')
