"""Admin email notifications for pending customer funding requests."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q

from user_management.services.email_branding import (
    BRAND_DEEP_INK,
    BRAND_NAME,
    BRAND_WARM_WHITE,
    BRAND_YELLOW,
)
from wallet.models import WalletTransaction

logger = logging.getLogger(__name__)


def resolve_funding_admin_emails() -> list[str]:
    """
    Active verified admins (ADMIN group + verified AdminProfile) and
    active superusers with a usable email.
    """
    qs = (
        User.objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(
                groups__name='ADMIN',
                admin_profile__is_verified=True,
            )
        )
        .exclude(email='')
        .exclude(email__isnull=True)
        .values_list('email', flat=True)
        .distinct()
    )
    emails = []
    seen = set()
    for email in qs:
        normalized = (email or '').strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        emails.append(email.strip())
    return emails


def _customer_display(txn: WalletTransaction) -> tuple[str, str]:
    customer = txn.wallet.customer
    user = customer.user
    name = (user.get_full_name() or user.username or '').strip() or 'Customer'
    identifier = (user.email or user.username or str(customer.public_id)).strip()
    return name, identifier


def _send_plain_admin_email(*, subject: str, body: str) -> None:
    recipients = resolve_funding_admin_emails()
    if not recipients:
        logger.warning('No funding admin recipients found; skipping notification.')
        return
    email = EmailMultiAlternatives(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
    )
    html = (
        f'<div style="font-family:Arial,sans-serif;color:{BRAND_DEEP_INK};'
        f'background:{BRAND_WARM_WHITE};padding:16px;">'
        f'<h2 style="color:{BRAND_DEEP_INK};border-bottom:3px solid {BRAND_YELLOW};'
        f'padding-bottom:8px;">{BRAND_NAME}</h2>'
        f'<pre style="white-space:pre-wrap;font-family:Arial,sans-serif;">{body}</pre>'
        f'</div>'
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


def notify_admins_pending_recharge(txn: WalletTransaction) -> None:
    name, identifier = _customer_display(txn)
    subject = f'[Befood] Pending wallet recharge {txn.public_id}'
    body = (
        f'This user submitted a wallet recharge request.\n\n'
        f'User name: {name}\n'
        f'User email/identifier: {identifier}\n'
        f'Amount: ৳{txn.amount}\n'
        f'Payment method: {txn.method}\n'
        f'Transaction ID: {txn.external_ref}\n'
        f'Request ID: {txn.public_id}\n'
        f'Submitted at: {txn.created_at.isoformat()}\n\n'
        f'Please verify the off-platform payment in the admin panel, '
        f'then approve or reject this request.'
    )
    _send_plain_admin_email(subject=subject, body=body)


def notify_admins_pending_withdraw(txn: WalletTransaction) -> None:
    name, identifier = _customer_display(txn)
    spendable = txn.wallet.balance
    subject = f'[Befood] Pending wallet withdraw {txn.public_id}'
    body = (
        f'This user submitted a wallet withdrawal request.\n\n'
        f'User name: {name}\n'
        f'User email/identifier: {identifier}\n'
        f'Withdrawal amount: ৳{txn.amount}\n'
        f'Request ID: {txn.public_id}\n'
        f'Submitted at: {txn.created_at.isoformat()}\n'
        f'Spendable balance after reservation: ৳{spendable}\n\n'
        f'Please send the payout manually, then approve this request '
        f'in the admin panel (or reject to release the reservation).'
    )
    _send_plain_admin_email(subject=subject, body=body)
