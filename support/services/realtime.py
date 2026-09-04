from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

ADMIN_INBOX_GROUP = 'support.admin.inbox'


def conversation_group_name(conversation_public_id) -> str:
    return f'support.conversation.{conversation_public_id}'


def serialize_message(message) -> dict:
    return {
        'public_id': str(message.public_id),
        'conversation_public_id': str(message.conversation.public_id),
        'sender_type': message.sender_type,
        'sender_user_id': message.sender_user_id,
        'body': message.body,
        'is_read_by_customer': message.is_read_by_customer,
        'is_read_by_admin': message.is_read_by_admin,
        'created_at': message.created_at.isoformat(),
    }


def serialize_conversation_summary(conversation) -> dict:
    customer = conversation.customer
    user = customer.user
    return {
        'public_id': str(conversation.public_id),
        'status': conversation.status,
        'last_message': conversation.last_message,
        'last_message_at': (
            conversation.last_message_at.isoformat() if conversation.last_message_at else None
        ),
        'customer_unread_count': conversation.customer_unread_count,
        'admin_unread_count': conversation.admin_unread_count,
        'customer': {
            'public_id': str(customer.public_id),
            'name': (user.get_full_name() or user.username or '').strip(),
            'phone': customer.phone or '',
            'email': user.email or '',
        },
    }


def broadcast_to_conversation(conversation_public_id, event_type: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        conversation_group_name(conversation_public_id),
        {
            'type': 'support.event',
            'event_type': event_type,
            'payload': payload,
        },
    )


def broadcast_admin_inbox(event_type: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        ADMIN_INBOX_GROUP,
        {
            'type': 'support.event',
            'event_type': event_type,
            'payload': payload,
        },
    )
