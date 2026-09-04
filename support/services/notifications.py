"""Best-effort offline alerts for support messaging (reuse FCM + admin email)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction

from notifications.services.device_service import get_user_device_tokens
from notifications.services.fcm_service import FCMNotConfiguredError, send_to_tokens
from notifications.services.inbox_service import create_inbox_notification
from support.models import SupportMessage
from support.services.presence import (
    is_admin_present_on_conversation,
    is_customer_present,
)
from wallet.services.funding_notifications import resolve_funding_admin_emails

logger = logging.getLogger(__name__)

SUPPORT_SCREEN = 'support_inbox'
SUPPORT_TYPE = 'support_reply'


def _customer_display(message: SupportMessage) -> tuple[str, str]:
    customer = message.conversation.customer
    user = customer.user
    name = (user.get_full_name() or user.username or '').strip() or 'Customer'
    identifier = (user.email or customer.phone or str(customer.public_id)).strip()
    return name, identifier


def notify_customer_of_admin_reply(message_id: int) -> None:
    try:
        message = SupportMessage.objects.select_related(
            'conversation',
            'conversation__customer',
            'conversation__customer__user',
        ).get(pk=message_id)
    except SupportMessage.DoesNotExist:
        return

    if message.sender_type != SupportMessage.SenderType.ADMIN:
        return

    conversation = message.conversation
    if is_customer_present(str(conversation.public_id)):
        logger.info(
            'Skip support FCM: customer online conversation=%s',
            conversation.public_id,
        )
        return

    user = conversation.customer.user
    title = 'BeFood Support'
    body = 'আপনার message এর reply এসেছে'
    data = {
        'type': SUPPORT_TYPE,
        'screen': SUPPORT_SCREEN,
        'conversation_public_id': str(conversation.public_id),
        'message_public_id': str(message.public_id),
    }
    try:
        create_inbox_notification(
            user,
            title=title,
            body=body,
            notification_type=SUPPORT_TYPE,
            screen=SUPPORT_SCREEN,
            data=data,
        )
        tokens = get_user_device_tokens(user)
        if not tokens:
            logger.info('Skip support FCM: no tokens user_id=%s', user.pk)
            return
        send_to_tokens(tokens, title, body, data)
    except FCMNotConfiguredError:
        logger.warning('FCM not configured; support customer push skipped')
    except Exception:
        logger.exception('Support customer push failed message_id=%s', message_id)


def notify_admins_of_customer_message(message_id: int) -> None:
    try:
        message = SupportMessage.objects.select_related(
            'conversation',
            'conversation__customer',
            'conversation__customer__user',
        ).get(pk=message_id)
    except SupportMessage.DoesNotExist:
        return

    if message.sender_type != SupportMessage.SenderType.CUSTOMER:
        return

    conversation = message.conversation
    if is_admin_present_on_conversation(str(conversation.public_id)):
        logger.info(
            'Skip support admin email: admin online conversation=%s',
            conversation.public_id,
        )
        return

    name, identifier = _customer_display(message)
    preview = message.body if len(message.body) <= 200 else f'{message.body[:197]}...'
    subject = f'[BeFood Support] New message from {name}'
    body = (
        f'Customer: {name}\n'
        f'Email/Phone: {identifier}\n'
        f'Conversation: {conversation.public_id}\n\n'
        f'Message:\n{preview}\n'
    )
    try:
        recipients = resolve_funding_admin_emails()
        if not recipients:
            logger.warning('No admin emails for support notification')
            return
        email = EmailMultiAlternatives(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
        )
        email.send(fail_silently=True)
    except Exception:
        logger.exception('Support admin email failed message_id=%s', message_id)


def schedule_offline_notifications(message: SupportMessage) -> None:
    message_id = message.pk

    def _run():
        if message.sender_type == SupportMessage.SenderType.ADMIN:
            notify_customer_of_admin_reply(message_id)
        elif message.sender_type == SupportMessage.SenderType.CUSTOMER:
            notify_admins_of_customer_message(message_id)

    transaction.on_commit(_run)
