"""Tests for customer notification inbox APIs and persistence."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from notifications.models import Notification
from notifications.services.inbox_service import create_inbox_notification
from notifications.services.fcm_service import _android_channel_id

User = get_user_model()


class InboxServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='inbox_u1',
            email='inbox1@example.com',
            password='pass12345',
        )

    def test_create_inbox_notification(self):
        row = create_inbox_notification(
            self.user,
            title='Hello',
            body='World',
            notification_type='wallet',
            screen='wallet',
            data={'type': 'wallet'},
        )
        self.assertIsNotNone(row)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertFalse(row.is_read)

    def test_android_channel_mapping(self):
        self.assertEqual(_android_channel_id({'type': 'wallet_low_balance'}), 'befood_wallet')
        self.assertEqual(_android_channel_id({'type': 'meal_delivered'}), 'befood_order')
        self.assertEqual(_android_channel_id({'type': 'promotion'}), 'befood_promotion')


class InboxApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='inbox_api_u1',
            email='inboxapi1@example.com',
            password='pass12345',
        )
        self.other = User.objects.create_user(
            username='inbox_api_u2',
            email='inboxapi2@example.com',
            password='pass12345',
        )
        self.mine = Notification.objects.create(
            user=self.user,
            title='Mine',
            body='Body',
            is_read=False,
            notification_type='wallet',
            screen='wallet',
        )
        Notification.objects.create(
            user=self.other,
            title='Other',
            body='Secret',
            is_read=False,
        )

    def test_list_scoped_to_user(self):
        self.client.force_authenticate(self.user)
        response = self.client.get('/notifications/inbox/')
        self.assertEqual(response.status_code, 200)
        data = response.data
        if isinstance(data, dict):
            results = data['results'] if 'results' in data else data
        else:
            results = list(data)
        titles = [item['title'] for item in results]
        self.assertIn('Mine', titles)
        self.assertNotIn('Other', titles)

    def test_unread_count(self):
        self.client.force_authenticate(self.user)
        response = self.client.get('/notifications/inbox/unread-count/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_mark_read(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(f'/notifications/inbox/{self.mine.pk}/read/')
        self.assertEqual(response.status_code, 200)
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_read)
        count = self.client.get('/notifications/inbox/unread-count/').data['count']
        self.assertEqual(count, 0)

    def test_cannot_mark_others(self):
        other_row = Notification.objects.get(user=self.other)
        self.client.force_authenticate(self.user)
        response = self.client.post(f'/notifications/inbox/{other_row.pk}/read/')
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_denied(self):
        response = self.client.get('/notifications/inbox/')
        self.assertIn(response.status_code, (401, 403))
