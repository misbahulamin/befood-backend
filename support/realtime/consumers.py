from __future__ import annotations

import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from support.models import SupportMessage
from support.services.conversations import get_conversation_by_public_id
from support.services.messages import EmptyMessageError, mark_read_by_admin, mark_read_by_customer, post_message
from support.services.notifications import schedule_offline_notifications
from support.services.presence import (
    mark_admin_offline,
    mark_admin_online,
    mark_customer_offline,
    mark_customer_online,
    refresh_presence,
)
from support.services.realtime import ADMIN_INBOX_GROUP, conversation_group_name
from user_management.services.admin_access import is_verified_admin

logger = logging.getLogger(__name__)


class SupportConversationConsumer(AsyncJsonWebsocketConsumer):
    conversation_public_id = None
    conversation_id = None
    is_admin = False
    role = None

    async def connect(self):
        user = self.scope.get('user')
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.conversation_public_id = self.scope['url_route']['kwargs']['conversation_public_id']
        conversation = await database_sync_to_async(get_conversation_by_public_id)(
            self.conversation_public_id
        )
        if conversation is None:
            await self.close(code=4404)
            return

        self.is_admin = await database_sync_to_async(is_verified_admin)(user)
        if self.is_admin:
            self.role = 'admin'
        else:
            profile = await database_sync_to_async(lambda: getattr(user, 'customer_profile', None))()
            if profile is None or profile.id != conversation.customer_id:
                await self.close(code=4403)
                return
            self.role = 'customer'

        self.conversation_id = conversation.id
        self.group_name = conversation_group_name(self.conversation_public_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        if self.is_admin:
            await self.channel_layer.group_add(ADMIN_INBOX_GROUP, self.channel_name)
            await database_sync_to_async(mark_admin_online)(
                user_id=user.id,
                conversation_public_id=str(self.conversation_public_id),
            )
        else:
            await database_sync_to_async(mark_customer_online)(
                user_id=user.id,
                conversation_public_id=str(self.conversation_public_id),
            )

        await self.accept()
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'support.event',
                'event_type': 'presence.online',
                'payload': {
                    'role': self.role,
                    'user_id': user.id,
                    'conversation_public_id': str(self.conversation_public_id),
                },
                'exclude_channel': self.channel_name,
            },
        )

    async def disconnect(self, code):
        user = self.scope.get('user')
        if self.conversation_public_id and user and user.is_authenticated:
            if self.is_admin:
                await database_sync_to_async(mark_admin_offline)(
                    user_id=user.id,
                    conversation_public_id=str(self.conversation_public_id),
                )
            else:
                await database_sync_to_async(mark_customer_offline)(
                    user_id=user.id,
                    conversation_public_id=str(self.conversation_public_id),
                )
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'support.event',
                        'event_type': 'presence.offline',
                        'payload': {
                            'role': self.role,
                            'user_id': user.id,
                            'conversation_public_id': str(self.conversation_public_id),
                        },
                        'exclude_channel': self.channel_name,
                    },
                )
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if self.is_admin:
            await self.channel_layer.group_discard(ADMIN_INBOX_GROUP, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get('user')
        event_type = (content or {}).get('type')
        payload = (content or {}).get('payload') or {}

        if event_type == 'message.send':
            await self._handle_message_send(user, payload)
        elif event_type == 'message.read':
            await self._handle_message_read(user)
        elif event_type in ('typing.start', 'typing.stop'):
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'support.event',
                    'event_type': event_type,
                    'payload': {
                        'role': self.role,
                        'user_id': user.id,
                        'conversation_public_id': str(self.conversation_public_id),
                    },
                    'exclude_channel': self.channel_name,
                },
            )
        elif event_type == 'presence.ping':
            await database_sync_to_async(refresh_presence)(
                user_id=user.id,
                is_admin=self.is_admin,
                conversation_public_id=str(self.conversation_public_id),
            )
        else:
            await self.send_json(
                {
                    'type': 'error',
                    'payload': {'detail': f'Unsupported event type: {event_type}'},
                }
            )

    async def _handle_message_send(self, user, payload):
        body = payload.get('message') or payload.get('body') or ''
        sender_type = (
            SupportMessage.SenderType.ADMIN
            if self.is_admin
            else SupportMessage.SenderType.CUSTOMER
        )

        def _create():
            conversation = get_conversation_by_public_id(self.conversation_public_id)
            if conversation is None:
                raise LookupError('Conversation not found')
            message = post_message(
                conversation=conversation,
                sender_type=sender_type,
                sender_user=user,
                body=body,
                broadcast=True,
            )
            schedule_offline_notifications(message)
            return message

        try:
            await database_sync_to_async(_create)()
        except EmptyMessageError as exc:
            await self.send_json({'type': 'error', 'payload': {'detail': str(exc)}})
        except LookupError:
            await self.close(code=4404)
        except Exception:
            logger.exception('WS message.send failed')
            await self.send_json({'type': 'error', 'payload': {'detail': 'Failed to send message'}})

    async def _handle_message_read(self, user):
        def _mark():
            conversation = get_conversation_by_public_id(self.conversation_public_id)
            if conversation is None:
                raise LookupError('Conversation not found')
            if self.is_admin:
                return mark_read_by_admin(conversation)
            return mark_read_by_customer(conversation)

        try:
            await database_sync_to_async(_mark)()
        except LookupError:
            await self.close(code=4404)

    async def support_event(self, event):
        if event.get('exclude_channel') == self.channel_name:
            return
        await self.send_json(
            {
                'type': event['event_type'],
                'payload': event.get('payload') or {},
            }
        )
