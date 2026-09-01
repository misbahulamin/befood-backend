from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from notifications.models import NotificationPreference, PushCampaign, PushCampaignRecipient
from notifications.services.fcm_service import SendResult
from notifications.services.notification_sender import BROADCAST_CONFIRMATION_THRESHOLD
from user_management.models import AdminProfile, CustomerProfile, DeviceToken, RiderProfile, StaffProfile


def _make_customer(username: str, email: str) -> User:
    user = User.objects.create_user(
        username=username,
        email=email,
        password='StrongPassword123',
        is_active=True,
    )
    suffix = str(abs(hash(email)))[-9:].zfill(9)
    CustomerProfile.objects.create(user=user, phone=f'1{suffix}')
    return user


class AdminPushNotificationAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin = User.objects.create_user(
            username='push-admin',
            email='push-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin, is_verified=True)
        self.admin.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin)

        self.customer = _make_customer('pushcust1', 'pushcust1@example.com')
        self.customer2 = _make_customer('pushcust2', 'pushcust2@example.com')
        self.customer_token = Token.objects.create(user=self.customer)

        self.device_token = 'd' * 140
        DeviceToken.objects.create(
            user=self.customer,
            token=self.device_token,
            platform='android',
            is_active=True,
        )

        self.send_url = reverse('web_notifications:admin-push-send')
        self.list_url = reverse('web_notifications:admin-push-campaign-list')

        self.send_payload = {
            'title': 'Hello',
            'body': 'Test notification body',
            'notification_type': 'system',
            'data': {
                'screen': 'order_detail',
                'entity_type': 'order',
                'entity_id': '123',
            },
            'target': {'type': 'user', 'user_id': self.customer.id},
        }

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _mock_fcm_success(self):
        return patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[SendResult(token=self.device_token, success=True, message_id='msg-1')],
        )

    def _sync_dispatch(self):
        return patch(
            'notifications.api.admin_notification_views.transaction.on_commit',
            side_effect=lambda func: func(),
        )

    def test_unauthenticated_send_returns_401(self):
        response = self.client.post(self.send_url, self.send_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_send_returns_403(self):
        self._auth_customer()
        response = self.client.post(self.send_url, self.send_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('notifications.api.admin_notification_views.transaction.on_commit', side_effect=lambda func: func())
    @patch('notifications.api.admin_notification_views.enqueue_dispatch')
    def test_verified_admin_send_returns_202(self, mock_enqueue, _mock_on_commit):
        self._auth_admin()
        response = self.client.post(self.send_url, self._unique_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], PushCampaign.Status.PROCESSING)
        mock_enqueue.assert_called_once()

    def _unique_payload(self, **overrides):
        import uuid

        payload = {
            **self.send_payload,
            'title': f'Hello {uuid.uuid4().hex[:8]}',
        }
        payload.update(overrides)
        return payload

    def test_send_to_single_user(self):
        self._auth_admin()
        with self._sync_dispatch(), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), self._mock_fcm_success():
            response = self.client.post(self.send_url, self._unique_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        campaign.refresh_from_db()
        self.assertEqual(campaign.target_type, PushCampaign.TargetType.SINGLE_USER)
        self.assertEqual(campaign.total_sent, 1)

    def test_send_to_selected_users(self):
        self._auth_admin()
        payload = {
            **self.send_payload,
            'target': {'type': 'users', 'user_ids': [self.customer.id, self.customer2.id]},
        }
        with self._sync_dispatch(), self._mock_fcm_success():
            response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        self.assertEqual(campaign.target_type, PushCampaign.TargetType.SELECTED_USERS)
        self.assertEqual(campaign.total_targets, 2)

    def test_send_to_filtered_users(self):
        self._auth_admin()
        payload = {
            **self.send_payload,
            'target': {'type': 'filter', 'filters': {'is_active': True}},
        }
        with self._sync_dispatch(), self._mock_fcm_success():
            response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        self.assertEqual(campaign.target_type, PushCampaign.TargetType.FILTERED_USERS)
        self.assertGreaterEqual(campaign.total_targets, 1)

    @override_settings()
    def test_send_to_all_requires_confirmation(self):
        self._auth_admin()
        with patch(
            'notifications.services.notification_sender.BROADCAST_CONFIRMATION_THRESHOLD',
            1,
        ):
            payload = {
                **self.send_payload,
                'target': {'type': 'all'},
            }
            response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rider_user_target_rejected(self):
        rider = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='StrongPassword123',
        )
        RiderProfile.objects.create(user=rider, phone='1712345678')
        self._auth_admin()
        payload = {**self.send_payload, 'target': {'type': 'user', 'user_id': rider.id}}
        response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_staff_user_target_rejected(self):
        staff = User.objects.create_user(
            username='staff1',
            email='staff1@example.com',
            password='StrongPassword123',
        )
        StaffProfile.objects.create(user=staff)
        self._auth_admin()
        payload = {**self.send_payload, 'target': {'type': 'user', 'user_id': staff.id}}
        response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_user_target_rejected(self):
        other_admin = User.objects.create_user(
            username='otheradmin',
            email='otheradmin@example.com',
            password='StrongPassword123',
        )
        AdminProfile.objects.create(user=other_admin, is_verified=True)
        self._auth_admin()
        payload = {**self.send_payload, 'target': {'type': 'user', 'user_id': other_admin.id}}
        response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_idempotency_key_returns_same_campaign(self):
        self._auth_admin()
        headers = {'HTTP_IDEMPOTENCY_KEY': 'key-abc-123'}
        with patch('notifications.api.admin_notification_views.enqueue_dispatch'):
            first = self.client.post(self.send_url, self.send_payload, format='json', **headers)
            second = self.client.post(self.send_url, self.send_payload, format='json', **headers)
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(first.data['public_id'], second.data['public_id'])
        self.assertEqual(PushCampaign.objects.count(), 1)

    def test_fingerprint_duplicate_returns_409(self):
        self._auth_admin()
        with patch('notifications.api.admin_notification_views.enqueue_dispatch'):
            first = self.client.post(self.send_url, self.send_payload, format='json')
            second = self.client.post(self.send_url, self.send_payload, format='json')
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(first.data['public_id'], second.data['public_id'])

    def test_unknown_data_key_rejected(self):
        self._auth_admin()
        payload = {
            **self.send_payload,
            'data': {'type': 'order', 'id': '123'},
        }
        response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_push_preference_opt_out_skipped(self):
        NotificationPreference.objects.create(user=self.customer, push_enabled=False)
        self._auth_admin()
        with self._sync_dispatch():
            response = self.client.post(self.send_url, self.send_payload, format='json')
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        self.assertEqual(campaign.total_skipped, 1)
        recipient = campaign.recipients.get(user=self.customer)
        self.assertEqual(recipient.status, PushCampaignRecipient.Status.SKIPPED)

    def test_partial_failure_completes_campaign(self):
        self._auth_admin()
        results = [
            SendResult(token=self.device_token, success=False, error='Temporary error'),
        ]
        with self._sync_dispatch(), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=results,
        ):
            response = self.client.post(self.send_url, self._unique_payload(), format='json')
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, PushCampaign.Status.COMPLETED)
        self.assertEqual(campaign.total_failed, 1)

    def test_invalid_token_deactivates_device(self):
        self._auth_admin()
        results = [
            SendResult(
                token=self.device_token,
                success=False,
                error='Requested entity was not found.',
                is_invalid_token=True,
            ),
        ]
        with self._sync_dispatch(), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=results,
        ):
            self.client.post(self.send_url, self._unique_payload(), format='json')
        device = DeviceToken.objects.get(token=self.device_token)
        self.assertFalse(device.is_active)

    def test_audit_fields_populated(self):
        self._auth_admin()
        with patch('notifications.api.admin_notification_views.enqueue_dispatch'):
            response = self.client.post(
                self.send_url,
                self.send_payload,
                format='json',
                HTTP_USER_AGENT='AdminPanel/1.0',
                REMOTE_ADDR='203.0.113.10',
            )
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        self.assertEqual(campaign.created_by_id, self.admin.id)
        self.assertEqual(str(campaign.ip_address), '203.0.113.10')
        self.assertIn('AdminPanel', campaign.user_agent)

    def test_campaign_list_and_detail(self):
        self._auth_admin()
        with patch('notifications.api.admin_notification_views.enqueue_dispatch'):
            created = self.client.post(self.send_url, self.send_payload, format='json')
        list_response = self.client.get(self.list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_response.data['count'], 1)

        detail_url = reverse(
            'web_notifications:admin-push-campaign-detail',
            kwargs={'public_id': created.data['public_id']},
        )
        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIn('recipients', detail_response.data)
        self.assertIn('total_skipped', detail_response.data)

    @patch('notifications.services.fcm_service._get_firebase_app')
    @patch('firebase_admin.messaging.send_each_for_multicast')
    def test_fcm_batching_splits_at_500(self, mock_multicast, _mock_app):
        class _FakeSendResponse:
            def __init__(self):
                self.success = True
                self.message_id = 'msg-1'
                self.exception = None

        class _FakeBatchResponse:
            def __init__(self, count):
                self.responses = [_FakeSendResponse() for _ in range(count)]

        mock_multicast.side_effect = lambda message, **kwargs: _FakeBatchResponse(len(message.tokens))

        tokens = [f'token-{index:04d}' for index in range(600)]
        from notifications.services.fcm_service import send_to_tokens

        send_to_tokens(tokens, 'Title', 'Body', {'screen': 'home'})
        self.assertEqual(mock_multicast.call_count, 2)
        batch_sizes = [len(call.args[0].tokens) for call in mock_multicast.call_args_list]
        self.assertEqual(batch_sizes, [500, 100])


class DispatchPushCampaignCommandTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            username='cmd-admin',
            email='cmd-admin@example.com',
            password='StrongPassword123',
        )
        self.campaign = PushCampaign.objects.create(
            title='Stuck',
            body='Body',
            notification_type='system',
            created_by=admin,
            target_type=PushCampaign.TargetType.SINGLE_USER,
            target_config={'type': 'user', 'user_id': 1},
            status=PushCampaign.Status.PROCESSING,
        )

    def test_management_command_stuck_only(self):
        from django.core.management import call_command

        with patch(
            'notifications.management.commands.dispatch_push_campaign.dispatch_push_campaign'
        ) as mock_dispatch, patch(
            'notifications.management.commands.dispatch_push_campaign.get_stuck_campaign_ids',
            return_value=[self.campaign.id],
        ):
            call_command('dispatch_push_campaign', '--stuck-only')
        mock_dispatch.assert_called_once_with(self.campaign.id)
