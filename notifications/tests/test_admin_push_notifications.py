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
        self.assertEqual(campaign.data.get('screen'), 'order_detail')
        self.assertEqual(campaign.data.get('entity_type'), 'order')
        self.assertEqual(campaign.data.get('entity_id'), '123')

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

    def test_non_invalid_fcm_error_keeps_device_active(self):
        """Transient / payload errors must not soft-deactivate healthy tokens."""
        self._auth_admin()
        results = [
            SendResult(
                token=self.device_token,
                success=False,
                error='Invalid argument: bad webpush config',
                is_invalid_token=False,
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
        self.assertTrue(device.is_active)

    def test_fcm_exception_after_inbox_leaves_terminal_status(self):
        """Inbox can succeed while FCM raises — campaign must not stay processing."""
        from notifications.models import Notification

        self._auth_admin()
        with self._sync_dispatch(), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            side_effect=RuntimeError('simulated firebase sdk crash'),
        ):
            response = self.client.post(self.send_url, self._unique_payload(), format='json')
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        campaign.refresh_from_db()
        self.assertNotEqual(campaign.status, PushCampaign.Status.PROCESSING)
        self.assertIn(
            campaign.status,
            {PushCampaign.Status.FAILED, PushCampaign.Status.COMPLETED},
        )
        self.assertEqual(campaign.total_sent, 0)
        self.assertGreaterEqual(campaign.total_failed, 1)
        self.assertEqual(
            Notification.objects.filter(user=self.customer, object_id=campaign.pk).count(),
            1,
        )
        recipient = campaign.recipients.get(user=self.customer)
        self.assertEqual(recipient.status, PushCampaignRecipient.Status.FAILED)
        self.assertTrue(recipient.error_message)

    def test_total_sent_counts_only_fcm_success_not_inbox(self):
        from notifications.models import Notification

        self._auth_admin()
        with self._sync_dispatch(), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[
                SendResult(token=self.device_token, success=False, error='quota exceeded'),
            ],
        ):
            response = self.client.post(self.send_url, self._unique_payload(), format='json')
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, PushCampaign.Status.COMPLETED)
        self.assertEqual(campaign.total_sent, 0)
        self.assertEqual(campaign.total_failed, 1)
        self.assertEqual(
            Notification.objects.filter(user=self.customer, object_id=campaign.pk).count(),
            1,
        )

        detail_url = reverse(
            'web_notifications:admin-push-campaign-detail',
            kwargs={'public_id': campaign.public_id},
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.data['total_sent'], 0)
        self.assertEqual(detail.data['status'], PushCampaign.Status.COMPLETED)

        list_response = self.client.get(self.list_url)
        match = next(
            item for item in list_response.data['results']
            if item['public_id'] == str(campaign.public_id)
        )
        self.assertEqual(match['total_sent'], 0)

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

    def test_detail_recipients_include_name_public_id_sent_at_and_is_read(self):
        from notifications.models import Notification

        self.customer.first_name = 'Raiyan'
        self.customer.last_name = 'Muntasir'
        self.customer.save(update_fields=['first_name', 'last_name'])

        self._auth_admin()
        with self._sync_dispatch(), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), self._mock_fcm_success():
            created = self.client.post(self.send_url, self._unique_payload(), format='json')

        campaign = PushCampaign.objects.get(public_id=created.data['public_id'])
        inbox = Notification.objects.get(user=self.customer, object_id=campaign.pk)
        self.assertFalse(inbox.is_read)

        detail_url = reverse(
            'web_notifications:admin-push-campaign-detail',
            kwargs={'public_id': campaign.public_id},
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        recipient = detail.data['recipients'][0]
        self.assertEqual(recipient['user_name'], 'Raiyan Muntasir')
        self.assertEqual(recipient['user_email'], self.customer.email)
        self.assertEqual(recipient['user_public_id'], str(self.customer.customer_profile.public_id))
        self.assertEqual(recipient['status'], PushCampaignRecipient.Status.SENT)
        self.assertIsNotNone(recipient['sent_at'])
        self.assertIs(recipient['is_read'], False)

        inbox.is_read = True
        inbox.save(update_fields=['is_read'])
        detail_after = self.client.get(detail_url)
        self.assertIs(detail_after.data['recipients'][0]['is_read'], True)

    def test_detail_is_read_null_without_inbox_link(self):
        self._auth_admin()
        campaign = PushCampaign.objects.create(
            title='Legacy',
            body='Body',
            notification_type='system',
            target_type=PushCampaign.TargetType.SINGLE_USER,
            target_config={'type': 'user', 'user_id': self.customer.id},
            created_by=self.admin,
            status=PushCampaign.Status.COMPLETED,
            total_targets=1,
            total_failed=1,
        )
        PushCampaignRecipient.objects.create(
            campaign=campaign,
            user=self.customer,
            status=PushCampaignRecipient.Status.FAILED,
            error_message='No active device',
        )
        detail_url = reverse(
            'web_notifications:admin-push-campaign-detail',
            kwargs={'public_id': campaign.public_id},
        )
        detail = self.client.get(detail_url)
        recipient = detail.data['recipients'][0]
        self.assertIsNone(recipient['is_read'])
        self.assertIsNone(recipient['sent_at'])
        self.assertEqual(recipient['user_name'], self.customer.email)

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

        send_to_tokens(
            tokens,
            'Title',
            'Body',
            {'screen': 'home'},
            token_platforms={token: 'android' for token in tokens},
        )
        self.assertEqual(mock_multicast.call_count, 2)
        batch_sizes = [len(call.args[0].tokens) for call in mock_multicast.call_args_list]
        self.assertEqual(batch_sizes, [500, 100])

    @patch('notifications.services.fcm_service._get_firebase_app')
    @patch('firebase_admin.messaging.send_each_for_multicast')
    def test_fcm_platform_split_native_vs_web(self, mock_multicast, _mock_app):
        class _FakeSendResponse:
            def __init__(self, success=True, error=None):
                self.success = success
                self.message_id = 'msg-1' if success else ''
                self.exception = error

        class _FakeBatchResponse:
            def __init__(self, responses):
                self.responses = responses

        android_token = 'a' * 140
        web_token = 'w' * 160

        def _side_effect(message, **kwargs):
            # Web batch: fail; native batch: succeed — proves isolation.
            if getattr(message, 'webpush', None) is not None:
                return _FakeBatchResponse(
                    [_FakeSendResponse(success=False, error=Exception('web push rejected'))]
                )
            return _FakeBatchResponse([_FakeSendResponse(success=True)])

        mock_multicast.side_effect = _side_effect
        from notifications.services.fcm_service import send_to_tokens

        results = send_to_tokens(
            [android_token, web_token],
            'Title',
            'Body',
            {'screen': 'home'},
            token_platforms={android_token: 'android', web_token: 'web'},
        )
        self.assertEqual(mock_multicast.call_count, 2)
        by_token = {r.token: r for r in results}
        self.assertTrue(by_token[android_token].success)
        self.assertFalse(by_token[web_token].success)

        # Native message must not attach WebpushConfig; web must not need AndroidConfig.
        native_msg = next(
            call.args[0]
            for call in mock_multicast.call_args_list
            if android_token in call.args[0].tokens
        )
        web_msg = next(
            call.args[0]
            for call in mock_multicast.call_args_list
            if web_token in call.args[0].tokens
        )
        self.assertIsNotNone(native_msg.android)
        self.assertIsNone(getattr(native_msg, 'webpush', None))
        self.assertIsNotNone(web_msg.webpush)

    def test_classify_error_narrow_invalid_markers(self):
        from notifications.services.fcm_service import _classify_error

        _, is_invalid_unreg = _classify_error(Exception('Requested entity was not found.'))
        self.assertTrue(is_invalid_unreg)
        _, is_invalid_arg = _classify_error(Exception('Invalid argument: bad payload'))
        self.assertFalse(is_invalid_arg)

    @patch('notifications.services.fcm_service._get_firebase_app')
    @patch('firebase_admin.messaging.send_each_for_multicast')
    def test_fcm_batch_exception_returns_controlled_failures(self, mock_multicast, _mock_app):
        mock_multicast.side_effect = RuntimeError('firebase internal boom')
        from notifications.services.fcm_service import send_to_tokens

        token = 'z' * 140
        results = send_to_tokens(
            [token],
            'Title',
            'Body',
            token_platforms={token: 'android'},
        )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)
        self.assertIn('FCM send error', results[0].error)
        self.assertFalse(results[0].is_invalid_token)


class AdminPushWebTokenDeliveryTests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin = User.objects.create_user(
            username='webpush-admin',
            email='webpush-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin, is_verified=True)
        self.admin.groups.add(admin_group)
        self.admin_token = Token.objects.create(user=self.admin)
        self.customer = _make_customer('webpushcust', 'webpushcust@example.com')
        self.android_token = 'a' * 140
        self.web_token = 'w' * 160
        DeviceToken.objects.create(
            user=self.customer,
            token=self.android_token,
            platform='android',
            is_active=True,
        )
        DeviceToken.objects.create(
            user=self.customer,
            token=self.web_token,
            platform='web',
            is_active=True,
        )
        self.send_url = reverse('web_notifications:admin-push-send')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def test_campaign_includes_android_and_web_tokens(self):
        captured = {}

        def _capture(tokens, title, body, data=None, **kwargs):
            captured['tokens'] = list(tokens)
            captured['token_platforms'] = kwargs.get('token_platforms')
            return [
                SendResult(token=t, success=True, message_id=f'm-{t[:4]}') for t in tokens
            ]

        payload = {
            'title': 'Multi device',
            'body': 'Reach android and web',
            'notification_type': 'system',
            'data': {'screen': 'home'},
            'target': {'type': 'user', 'user_id': self.customer.id},
            'idempotency_key': 'web-android-both-1',
        }
        with patch(
            'notifications.api.admin_notification_views.transaction.on_commit',
            side_effect=lambda func: func(),
        ), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            side_effect=_capture,
        ):
            response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn(self.android_token, captured.get('tokens', []))
        self.assertIn(self.web_token, captured.get('tokens', []))

    def test_inbox_created_without_device_tokens(self):
        from notifications.models import Notification

        bare = _make_customer('nodevice', 'nodevice@example.com')
        payload = {
            'title': 'Inbox only',
            'body': 'No FCM token needed',
            'notification_type': 'system',
            'data': {'screen': 'home'},
            'target': {'type': 'user', 'user_id': bare.id},
            'idempotency_key': 'inbox-no-device-1',
        }
        with patch(
            'notifications.api.admin_notification_views.transaction.on_commit',
            side_effect=lambda func: func(),
        ), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[],
        ):
            response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            Notification.objects.filter(user=bare, title='Inbox only').count(),
            1,
        )

    def test_multi_device_single_inbox_row(self):
        from notifications.models import Notification

        payload = {
            'title': 'One inbox',
            'body': 'Two devices',
            'notification_type': 'system',
            'data': {'screen': 'home'},
            'target': {'type': 'user', 'user_id': self.customer.id},
            'idempotency_key': 'multi-device-inbox-1',
        }
        with patch(
            'notifications.api.admin_notification_views.transaction.on_commit',
            side_effect=lambda func: func(),
        ), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[
                SendResult(token=self.android_token, success=True, message_id='m1'),
                SendResult(token=self.web_token, success=True, message_id='m2'),
            ],
        ):
            response = self.client.post(self.send_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            Notification.objects.filter(user=self.customer, title='One inbox').count(),
            1,
        )

    def test_redispatch_does_not_duplicate_inbox(self):
        from notifications.models import Notification
        from notifications.services.notification_sender import dispatch_push_campaign

        payload = {
            'title': 'Dedupe inbox',
            'body': 'Stuck recovery',
            'notification_type': 'system',
            'data': {'screen': 'home'},
            'target': {'type': 'user', 'user_id': self.customer.id},
            'idempotency_key': 'redispatch-inbox-1',
        }
        with patch(
            'notifications.api.admin_notification_views.transaction.on_commit',
            side_effect=lambda func: func(),
        ), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[
                SendResult(token=self.android_token, success=True, message_id='m1'),
                SendResult(token=self.web_token, success=True, message_id='m2'),
            ],
        ):
            response = self.client.post(self.send_url, payload, format='json')
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        self.assertEqual(
            Notification.objects.filter(user=self.customer, object_id=campaign.pk).count(),
            1,
        )

        # Simulate stuck recovery: reset still-pending-style re-entry by forcing
        # processing and re-running dispatch (inbox must stay one row).
        campaign.status = PushCampaign.Status.PROCESSING
        campaign.save(update_fields=['status', 'updated_at'])
        with patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[],
        ):
            dispatch_push_campaign(campaign.id)
        self.assertEqual(
            Notification.objects.filter(user=self.customer, object_id=campaign.pk).count(),
            1,
        )

    def test_mixed_android_success_web_failure_counters(self):
        payload = {
            'title': 'Mixed platforms',
            'body': 'Native ok web fail',
            'notification_type': 'system',
            'data': {'screen': 'home'},
            'target': {'type': 'user', 'user_id': self.customer.id},
            'idempotency_key': 'mixed-platform-1',
        }
        with patch(
            'notifications.api.admin_notification_views.transaction.on_commit',
            side_effect=lambda func: func(),
        ), patch(
            'notifications.api.admin_notification_views.enqueue_dispatch',
            side_effect=lambda campaign_id: __import__(
                'notifications.services.notification_sender', fromlist=['dispatch_push_campaign']
            ).dispatch_push_campaign(campaign_id),
        ), patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[
                SendResult(token=self.android_token, success=True, message_id='m-android'),
                SendResult(token=self.web_token, success=False, error='web rejected'),
            ],
        ):
            response = self.client.post(self.send_url, payload, format='json')
        campaign = PushCampaign.objects.get(public_id=response.data['public_id'])
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, PushCampaign.Status.COMPLETED)
        self.assertEqual(campaign.total_sent, 1)
        self.assertEqual(campaign.total_failed, 1)
        self.assertEqual(
            campaign.recipients.get(device__token=self.android_token).status,
            PushCampaignRecipient.Status.SENT,
        )
        self.assertEqual(
            campaign.recipients.get(device__token=self.web_token).status,
            PushCampaignRecipient.Status.FAILED,
        )


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

    def test_stuck_only_resumes_pending_recipients_with_hardened_dispatcher(self):
        """End-to-end: --stuck-only re-enters dispatch and finalizes pending FCM rows."""
        from django.core.management import call_command
        from django.utils import timezone
        from datetime import timedelta

        customer = _make_customer('stuckcust', 'stuckcust@example.com')
        device_token = 's' * 140
        device = DeviceToken.objects.create(
            user=customer,
            token=device_token,
            platform='android',
            is_active=True,
        )
        # Bypass auto_now so the campaign qualifies as stuck.
        PushCampaign.objects.filter(pk=self.campaign.pk).update(
            updated_at=timezone.now() - timedelta(minutes=60),
        )
        PushCampaignRecipient.objects.create(
            campaign=self.campaign,
            user=customer,
            device=device,
            status=PushCampaignRecipient.Status.PENDING,
        )

        with patch(
            'notifications.services.notification_sender.send_to_tokens',
            return_value=[SendResult(token=device_token, success=True, message_id='stuck-1')],
        ):
            call_command('dispatch_push_campaign', '--stuck-only')

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, PushCampaign.Status.COMPLETED)
        self.assertEqual(self.campaign.total_sent, 1)
        recipient = self.campaign.recipients.get(user=customer)
        self.assertEqual(recipient.status, PushCampaignRecipient.Status.SENT)
