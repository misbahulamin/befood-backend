from unittest.mock import patch

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.asgi import application
from support.models import SupportConversation, SupportMessage
from support.services.messages import post_message
from support.services.notifications import (
    notify_admins_of_customer_message,
    notify_customer_of_admin_reply,
)
from support.services.presence import (
    is_customer_present,
    mark_customer_online,
    mark_admin_online,
)
from user_management.models import AdminProfile, CustomerProfile


def _make_customer(username: str, email: str, phone: str) -> User:
    user = User.objects.create_user(
        username=username,
        email=email,
        password='StrongPassword123',
        first_name='Test',
        last_name='Customer',
        is_active=True,
    )
    CustomerProfile.objects.create(user=user, phone=phone)
    return user


def _make_admin(username: str, email: str) -> User:
    group, _ = Group.objects.get_or_create(name='ADMIN')
    user = User.objects.create_user(
        username=username,
        email=email,
        password='StrongPassword123',
        is_active=True,
    )
    AdminProfile.objects.create(user=user, is_verified=True)
    user.groups.add(group)
    return user


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class SupportRestAPITests(APITestCase):
    def setUp(self):
        self.customer = _make_customer('supcust', 'supcust@example.com', '1711111111')
        self.other = _make_customer('supother', 'supother@example.com', '1722222222')
        self.admin = _make_admin('supadmin', 'supadmin@example.com')
        self.customer_token = Token.objects.create(user=self.customer)
        self.other_token = Token.objects.create(user=self.other)
        self.admin_token = Token.objects.create(user=self.admin)
        self.inbox_url = '/api/v1/support/inbox/'
        self.messages_url = '/api/v1/support/messages/'
        self.admin_list_url = '/api/v1/web/support/conversations/'

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_unauthenticated_inbox_401(self):
        response = self.client.get(self.inbox_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_send_and_inbox_history(self):
        self._auth(self.customer_token)
        create = self.client.post(self.messages_url, {'message': 'Lunch missing'}, format='json')
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SupportConversation.objects.filter(customer=self.customer.customer_profile).count(), 1)

        create2 = self.client.post(self.messages_url, {'message': 'Please help'}, format='json')
        self.assertEqual(create2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SupportConversation.objects.filter(customer=self.customer.customer_profile).count(), 1)

        inbox = self.client.get(self.inbox_url)
        self.assertEqual(inbox.status_code, status.HTTP_200_OK)
        bodies = [m['body'] for m in inbox.data['messages']]
        self.assertEqual(bodies, ['Lunch missing', 'Please help'])
        self.assertEqual(inbox.data['conversation']['customer_unread_count'], 0)

    def test_empty_message_rejected(self):
        self._auth(self.customer_token)
        response = self.client.post(self.messages_url, {'message': '   '}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_list_reply_status(self):
        self._auth(self.customer_token)
        self.client.post(self.messages_url, {'message': 'Payment issue'}, format='json')
        conversation = SupportConversation.objects.get(customer=self.customer.customer_profile)

        self._auth(self.admin_token)
        listing = self.client.get(self.admin_list_url)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(listing.data['count'], 1)
        row = listing.data['results'][0]
        self.assertIn('customer_name', row)
        self.assertIn('customer_phone', row)
        self.assertIn('admin_unread_count', row)

        filtered = self.client.get(self.admin_list_url, {'status': 'open', 'has_unread': 'true'})
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)

        detail = self.client.get(f'{self.admin_list_url}{conversation.public_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['messages'][0]['body'], 'Payment issue')

        reply = self.client.post(
            f'{self.admin_list_url}{conversation.public_id}/reply/',
            {'message': 'We are checking'},
            format='json',
        )
        self.assertEqual(reply.status_code, status.HTTP_201_CREATED)

        status_resp = self.client.patch(
            f'{self.admin_list_url}{conversation.public_id}/status/',
            {'status': 'closed'},
            format='json',
        )
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(status_resp.data['status'], 'closed')

    def test_customer_denied_admin_api(self):
        self._auth(self.customer_token)
        response = self.client.get(self.admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_messages_never_deleted_via_api(self):
        self._auth(self.customer_token)
        self.client.post(self.messages_url, {'message': 'Keep me'}, format='json')
        msg = SupportMessage.objects.get()
        delete = self.client.delete(f'/api/v1/support/messages/{msg.public_id}/')
        self.assertIn(delete.status_code, (status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED))
        self.assertTrue(SupportMessage.objects.filter(pk=msg.pk).exists())


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SupportNotificationTests(APITestCase):
    def setUp(self):
        self.customer = _make_customer('supnotify', 'supnotify@example.com', '1733333333')
        self.admin = _make_admin('supnotifyadmin', 'supnotifyadmin@example.com')
        self.conversation = SupportConversation.objects.create(
            customer=self.customer.customer_profile
        )

    @patch('support.services.notifications.send_to_tokens')
    @patch('support.services.notifications.get_user_device_tokens', return_value=['tok'])
    @patch('support.services.notifications.create_inbox_notification')
    def test_admin_reply_notifies_offline_customer(self, mock_inbox, mock_tokens, mock_send):
        message = post_message(
            conversation=self.conversation,
            sender_type=SupportMessage.SenderType.ADMIN,
            sender_user=self.admin,
            body='Reply body',
            broadcast=False,
        )
        notify_customer_of_admin_reply(message.pk)
        mock_inbox.assert_called_once()
        mock_send.assert_called_once()

    @patch('support.services.notifications.send_to_tokens')
    @patch('support.services.notifications.create_inbox_notification')
    def test_skip_fcm_when_customer_online(self, mock_inbox, mock_send):
        mark_customer_online(
            user_id=self.customer.id,
            conversation_public_id=str(self.conversation.public_id),
        )
        message = post_message(
            conversation=self.conversation,
            sender_type=SupportMessage.SenderType.ADMIN,
            sender_user=self.admin,
            body='Live reply',
            broadcast=False,
        )
        notify_customer_of_admin_reply(message.pk)
        mock_inbox.assert_not_called()
        mock_send.assert_not_called()

    def test_customer_message_emails_admins_when_offline(self):
        message = post_message(
            conversation=self.conversation,
            sender_type=SupportMessage.SenderType.CUSTOMER,
            sender_user=self.customer,
            body='Need help',
            broadcast=False,
        )
        notify_admins_of_customer_message(message.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Need help', mail.outbox[0].body)

    def test_skip_email_when_admin_online(self):
        mark_admin_online(
            user_id=self.admin.id,
            conversation_public_id=str(self.conversation.public_id),
        )
        message = post_message(
            conversation=self.conversation,
            sender_type=SupportMessage.SenderType.CUSTOMER,
            sender_user=self.customer,
            body='Online admins',
            broadcast=False,
        )
        notify_admins_of_customer_message(message.pk)
        self.assertEqual(len(mail.outbox), 0)

    @patch(
        'support.services.notifications.send_to_tokens',
        side_effect=RuntimeError('boom'),
    )
    @patch('support.services.notifications.get_user_device_tokens', return_value=['tok'])
    @patch('support.services.notifications.create_inbox_notification')
    def test_fcm_failure_does_not_delete_message(self, mock_inbox, mock_tokens, mock_send):
        message = post_message(
            conversation=self.conversation,
            sender_type=SupportMessage.SenderType.ADMIN,
            sender_user=self.admin,
            body='Still saved',
            broadcast=False,
        )
        notify_customer_of_admin_reply(message.pk)
        self.assertTrue(SupportMessage.objects.filter(pk=message.pk).exists())


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    ALLOWED_HOSTS=['*'],
)
class SupportWebsocketTests(TransactionTestCase):
    def setUp(self):
        self.customer = _make_customer('wscust', 'wscust@example.com', '1744444444')
        self.other = _make_customer('wsother', 'wsother@example.com', '1755555555')
        self.admin = _make_admin('wsadmin', 'wsadmin@example.com')
        self.customer_token = Token.objects.create(user=self.customer).key
        self.other_token = Token.objects.create(user=self.other).key
        self.admin_token = Token.objects.create(user=self.admin).key
        self.conversation = SupportConversation.objects.create(
            customer=self.customer.customer_profile
        )

    def _ws(self, token: str | None = None):
        path = f'/ws/support/{self.conversation.public_id}/'
        if token:
            path = f'{path}?token={token}'
        return WebsocketCommunicator(
            application,
            path,
            headers=[(b'origin', b'http://localhost')],
        )

    async def test_unauthenticated_ws_rejected(self):
        communicator = self._ws()
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4401)

    async def test_cross_customer_ws_denied(self):
        communicator = self._ws(self.other_token)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    async def test_customer_ws_message_persists(self):
        communicator = self._ws(self.customer_token)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        before = await database_sync_to_async(SupportMessage.objects.count)()
        await communicator.send_json_to(
            {'type': 'message.send', 'payload': {'message': 'Hello from WS'}}
        )
        # Allow consumer DB work to finish.
        event = await communicator.receive_json_from(timeout=5)
        # May be presence echo from another connection or own message.receive
        self.assertIn(event['type'], ('message.receive', 'presence.online', 'presence.offline'))

        # Poll DB until message lands (broadcast is sync inside consumer).
        for _ in range(20):
            after = await database_sync_to_async(SupportMessage.objects.count)()
            if after == before + 1:
                break
            await database_sync_to_async(lambda: None)()
        after = await database_sync_to_async(SupportMessage.objects.count)()
        self.assertEqual(after, before + 1)
        body = await database_sync_to_async(
            lambda: SupportMessage.objects.latest('id').body
        )()
        self.assertEqual(body, 'Hello from WS')

        present = await database_sync_to_async(is_customer_present)(
            str(self.conversation.public_id)
        )
        self.assertTrue(present)
        await communicator.disconnect()

    async def test_typing_does_not_create_rows(self):
        admin_ws = self._ws(self.admin_token)
        customer_ws = self._ws(self.customer_token)
        self.assertTrue((await admin_ws.connect())[0])
        self.assertTrue((await customer_ws.connect())[0])

        before = await database_sync_to_async(SupportMessage.objects.count)()
        await customer_ws.send_json_to({'type': 'typing.start', 'payload': {}})

        got_typing = False
        for _ in range(5):
            event = await admin_ws.receive_json_from(timeout=3)
            if event.get('type') == 'typing.start':
                got_typing = True
                break
        self.assertTrue(got_typing)
        after = await database_sync_to_async(SupportMessage.objects.count)()
        self.assertEqual(after, before)

        await customer_ws.disconnect()
        await admin_ws.disconnect()
