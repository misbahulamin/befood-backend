"""Best-effort customer push + invoice email after recharge approval."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from notifications.services.device_service import get_user_device_tokens
from notifications.services.fcm_service import FCMNotConfiguredError, send_to_tokens
from user_management.services.email_branding import build_brand_email_context
from wallet.models import WalletTransaction
from wallet.services.transaction_invoice import build_invoice_context

logger = logging.getLogger(__name__)

# Mobile deep-link screen key (documented for befood_mobile).
RECHARGE_APPROVED_SCREEN = 'wallet'


def _format_amount(value) -> str:
    return f'{value:.2f}'


def _send_recharge_approved_push(*, user, txn: WalletTransaction, amount, balance) -> None:
    tokens = get_user_device_tokens(user)
    if not tokens:
        logger.info(
            'Skipping recharge-approved push: no tokens user_id=%s txn=%s',
            getattr(user, 'pk', None),
            txn.public_id,
        )
        return

    amount_s = _format_amount(amount)
    balance_s = _format_amount(balance)
    reviewed_at = txn.reviewed_at or timezone.now()
    title = 'Wallet recharge approved'
    body = (
        f'Your wallet recharge of ৳{amount_s} has been approved successfully. '
        f'Your updated balance is ৳{balance_s}.'
    )
    data = {
        'type': 'wallet_recharge_approved',
        'screen': RECHARGE_APPROVED_SCREEN,
        'entity_type': 'wallet_transaction',
        'entity_id': str(txn.public_id),
        'amount': amount_s,
        'balance': balance_s,
        'invoice_number': txn.invoice_number or '',
        'approved_at': timezone.localtime(reviewed_at).isoformat(),
    }
    send_to_tokens(tokens, title, body, data)


def _send_recharge_invoice_email(*, user, txn: WalletTransaction) -> None:
    email_addr = (getattr(user, 'email', None) or '').strip()
    if not email_addr:
        logger.info(
            'Skipping recharge invoice email: no address user_id=%s txn=%s',
            getattr(user, 'pk', None),
            txn.public_id,
        )
        return

    invoice = build_invoice_context(txn)
    context = build_brand_email_context(user, extra=invoice)
    subject = render_to_string(
        'emails/wallet_recharge_invoice_subject.txt',
        context,
    ).strip()
    text_body = render_to_string('emails/wallet_recharge_invoice_email.txt', context)
    html_body = render_to_string('emails/wallet_recharge_invoice_email.html', context)
    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [email_addr],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)


def notify_customer_recharge_approved(txn_id: int) -> None:
    """
    Send FCM push then branded invoice email for a completed recharge.

    Never raises into callers — approval credit must stay committed.
    Push and email failures are isolated from each other.
    """
    try:
        txn = WalletTransaction.objects.select_related(
            'wallet__customer__user',
        ).get(pk=txn_id)
    except WalletTransaction.DoesNotExist:
        logger.warning('Recharge notify skipped: txn_id=%s missing', txn_id)
        return

    if txn.type != WalletTransaction.Type.RECHARGE:
        logger.info('Recharge notify skipped: not a recharge txn=%s', txn.public_id)
        return
    if txn.status != WalletTransaction.Status.COMPLETED:
        logger.info(
            'Recharge notify skipped: status=%s txn=%s',
            txn.status,
            txn.public_id,
        )
        return

    try:
        user = txn.wallet.customer.user
    except Exception:
        logger.exception('Recharge notify failed loading user txn=%s', txn.public_id)
        return

    amount = txn.amount
    balance = txn.balance_after if txn.balance_after is not None else txn.wallet.balance

    try:
        _send_recharge_approved_push(user=user, txn=txn, amount=amount, balance=balance)
    except FCMNotConfiguredError:
        logger.info(
            'FCM not configured; skipped recharge-approved push txn=%s',
            txn.public_id,
        )
    except Exception:
        logger.exception('Recharge-approved push failed txn=%s', txn.public_id)

    try:
        _send_recharge_invoice_email(user=user, txn=txn)
    except Exception:
        logger.exception('Recharge invoice email failed txn=%s', txn.public_id)
