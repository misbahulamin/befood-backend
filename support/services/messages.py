from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from support.models import SupportConversation, SupportMessage
from support.services.realtime import (
    broadcast_admin_inbox,
    broadcast_to_conversation,
    serialize_conversation_summary,
    serialize_message,
)


class EmptyMessageError(ValueError):
    pass


def _max_length() -> int:
    return int(getattr(settings, 'SUPPORT_MESSAGE_MAX_LENGTH', 5000) or 5000)


def _normalize_body(body: str) -> str:
    text = (body or '').strip()
    if not text:
        raise EmptyMessageError('Message body is required.')
    max_len = _max_length()
    if len(text) > max_len:
        raise EmptyMessageError(f'Message body must be at most {max_len} characters.')
    return text


def _preview(body: str) -> str:
    return body if len(body) <= 255 else f'{body[:252]}...'


def _broadcast_message(message: SupportMessage) -> None:
    payload = serialize_message(message)
    broadcast_to_conversation(message.conversation.public_id, 'message.receive', payload)
    broadcast_admin_inbox(
        'conversation.updated',
        serialize_conversation_summary(message.conversation),
    )


@transaction.atomic
def post_message(
    *,
    conversation: SupportConversation,
    sender_type: str,
    sender_user,
    body: str,
    broadcast: bool = True,
) -> SupportMessage:
    text = _normalize_body(body)
    now = timezone.now()

    if sender_type == SupportMessage.SenderType.CUSTOMER:
        is_read_by_customer = True
        is_read_by_admin = False
    elif sender_type == SupportMessage.SenderType.ADMIN:
        is_read_by_customer = False
        is_read_by_admin = True
    else:
        is_read_by_customer = False
        is_read_by_admin = False

    message = SupportMessage.objects.create(
        conversation=conversation,
        sender_type=sender_type,
        sender_user=sender_user,
        body=text,
        is_read_by_customer=is_read_by_customer,
        is_read_by_admin=is_read_by_admin,
        created_at=now,
    )

    updates = {
        'last_message': _preview(text),
        'last_message_at': now,
        'updated_at': now,
    }
    conversation.last_message = updates['last_message']
    conversation.last_message_at = now

    if sender_type == SupportMessage.SenderType.CUSTOMER:
        SupportConversation.objects.filter(pk=conversation.pk).update(
            last_message=updates['last_message'],
            last_message_at=now,
            updated_at=now,
            admin_unread_count=F('admin_unread_count') + 1,
        )
        conversation.refresh_from_db(
            fields=['admin_unread_count', 'last_message', 'last_message_at', 'updated_at']
        )
    elif sender_type == SupportMessage.SenderType.ADMIN:
        SupportConversation.objects.filter(pk=conversation.pk).update(
            last_message=updates['last_message'],
            last_message_at=now,
            updated_at=now,
            customer_unread_count=F('customer_unread_count') + 1,
        )
        conversation.refresh_from_db(
            fields=['customer_unread_count', 'last_message', 'last_message_at', 'updated_at']
        )
    else:
        SupportConversation.objects.filter(pk=conversation.pk).update(**updates)
        conversation.refresh_from_db(fields=['last_message', 'last_message_at', 'updated_at'])

    if broadcast:
        _broadcast_message(message)

    return message


@transaction.atomic
def mark_read_by_customer(conversation: SupportConversation) -> SupportConversation:
    SupportMessage.objects.filter(
        conversation=conversation,
        is_read_by_customer=False,
    ).exclude(sender_type=SupportMessage.SenderType.CUSTOMER).update(is_read_by_customer=True)
    conversation.customer_unread_count = 0
    conversation.save(update_fields=['customer_unread_count', 'updated_at'])
    payload = {
        'conversation_public_id': str(conversation.public_id),
        'reader': 'customer',
        'customer_unread_count': 0,
        'admin_unread_count': conversation.admin_unread_count,
    }
    broadcast_to_conversation(conversation.public_id, 'message.read', payload)
    broadcast_admin_inbox('conversation.updated', serialize_conversation_summary(conversation))
    return conversation


@transaction.atomic
def mark_read_by_admin(conversation: SupportConversation) -> SupportConversation:
    SupportMessage.objects.filter(
        conversation=conversation,
        is_read_by_admin=False,
    ).exclude(sender_type=SupportMessage.SenderType.ADMIN).update(is_read_by_admin=True)
    conversation.admin_unread_count = 0
    conversation.save(update_fields=['admin_unread_count', 'updated_at'])
    payload = {
        'conversation_public_id': str(conversation.public_id),
        'reader': 'admin',
        'customer_unread_count': conversation.customer_unread_count,
        'admin_unread_count': 0,
    }
    broadcast_to_conversation(conversation.public_id, 'message.read', payload)
    broadcast_admin_inbox('conversation.updated', serialize_conversation_summary(conversation))
    return conversation
