from datetime import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import resolve
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile

from delivery_schedules.api.views import (
    DeliveryScheduleAdminViewSet,
    PublicDeliveryScheduleViewSet,
)
from delivery_schedules.models import DeliverySchedule

User = get_user_model()


def _make_schedule(**overrides) -> DeliverySchedule:
    defaults = {
        'name': 'Lunch',
        'start_time': time(12, 30),
        'end_time': time(14, 30),
        'is_active': True,
        'sort_order': 1,
    }
    defaults.update(overrides)
    schedule = DeliverySchedule(**defaults)
    schedule.full_clean()
    schedule.save()
    return schedule


class DeliveryScheduleAuthMixin:
    def setUp(self):
        DeliverySchedule.objects.all().delete()

        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='ds-admin',
            email='ds-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='ds-customer',
            email='ds-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345688',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.list_url = reverse('delivery_schedules:schedules-list')
        self.public_url = reverse('delivery_schedules:public-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _detail(self, public_id):
        return reverse(
            'delivery_schedules:schedules-detail',
            kwargs={'public_id': public_id},
        )


class DeliveryScheduleAdminAPITests(DeliveryScheduleAuthMixin, APITestCase):
    def test_url_resolution(self):
        self.assertEqual(
            resolve('/delivery-schedules/public/').func.cls,
            PublicDeliveryScheduleViewSet,
        )
        self.assertEqual(
            resolve('/delivery-schedules/').func.cls,
            DeliveryScheduleAdminViewSet,
        )

    def test_anonymous_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_list_update_delete(self):
        self._auth_admin()
        create = self.client.post(
            self.list_url,
            {
                'name': 'Breakfast',
                'start_time': '08:00:00',
                'end_time': '10:00:00',
                'is_active': True,
                'sort_order': 0,
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        public_id = create.data['public_id']
        self.assertEqual(create.data['name'], 'Breakfast')

        listing = self.client.get(self.list_url)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        results = listing.data.get('results', listing.data)
        self.assertTrue(any(row['public_id'] == public_id for row in results))

        patch = self.client.patch(
            self._detail(public_id),
            {'end_time': '10:30:00', 'is_active': False},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['end_time'], '10:30:00')
        self.assertFalse(patch.data['is_active'])

        delete = self.client.delete(self._detail(public_id))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeliverySchedule.objects.filter(public_id=public_id).exists())

    def test_blank_name_rejected(self):
        self._auth_admin()
        response = self.client.post(
            self.list_url,
            {
                'name': '   ',
                'start_time': '08:00:00',
                'end_time': '10:00:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_duplicate_name_rejected(self):
        _make_schedule(name='Lunch')
        self._auth_admin()
        response = self.client.post(
            self.list_url,
            {
                'name': 'lunch',
                'start_time': '11:00:00',
                'end_time': '13:00:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_overnight_window_rejected(self):
        self._auth_admin()
        response = self.client.post(
            self.list_url,
            {
                'name': 'Late Night',
                'start_time': '22:00:00',
                'end_time': '01:00:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_time', response.data)

    def test_equal_times_rejected(self):
        self._auth_admin()
        response = self.client.post(
            self.list_url,
            {
                'name': 'Instant',
                'start_time': '12:00:00',
                'end_time': '12:00:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_time', response.data)

    def test_admin_list_includes_inactive(self):
        _make_schedule(name='Lunch', is_active=True, sort_order=1)
        _make_schedule(
            name='Snacks',
            start_time=time(16, 0),
            end_time=time(17, 0),
            is_active=False,
            sort_order=3,
        )
        self._auth_admin()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        names = {row['name'] for row in results}
        self.assertEqual(names, {'Lunch', 'Snacks'})


class DeliverySchedulePublicAPITests(DeliveryScheduleAuthMixin, APITestCase):
    def test_public_returns_active_ordered(self):
        _make_schedule(name='Dinner', start_time=time(19, 0), end_time=time(21, 0), sort_order=2)
        _make_schedule(name='Lunch', start_time=time(12, 30), end_time=time(14, 30), sort_order=1)
        _make_schedule(
            name='Breakfast',
            start_time=time(8, 0),
            end_time=time(10, 0),
            is_active=False,
            sort_order=0,
        )

        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row['name'] for row in response.data], ['Lunch', 'Dinner'])
        self.assertEqual(
            set(response.data[0].keys()),
            {'public_id', 'name', 'start_time', 'end_time', 'sort_order'},
        )

    def test_public_empty(self):
        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_public_write_not_allowed(self):
        response = self.client.post(
            self.public_url,
            {
                'name': 'Hack',
                'start_time': '08:00:00',
                'end_time': '09:00:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
