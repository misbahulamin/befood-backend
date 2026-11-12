"""Admin digest for active subscribers missing delivery sub-location."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from html import escape
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import QuerySet
from django.utils import timezone

from orders.models import CustomerSubscription
from orders.services.wallet_balance_thresholds import customer_display_name, customer_phone
from user_management.services.email_branding import (
    BRAND_DEEP_INK,
    BRAND_NAME,
    BRAND_WARM_WHITE,
    BRAND_YELLOW,
)
from wallet.services.funding_notifications import resolve_funding_admin_emails

logger = logging.getLogger(__name__)

BUSINESS_TZ = ZoneInfo('Asia/Dhaka')
PLACEHOLDER = 'N/A'
VALID_SLOTS = frozenset({'evening', 'night'})


@dataclass
class UnassignedDigestRow:
    customer_id: int
    name: str
    phone: str
    subscription_time: str
    email: str


@dataclass
class UnassignedDigestRunResult:
    dry_run: bool = False
    slot: str | None = None
    candidate_count: int = 0
    email_sent: bool = False
    errors: int = 0
    rows: list[UnassignedDigestRow] = field(default_factory=list)

    def as_log_dict(self) -> dict:
        return {
            'dry_run': self.dry_run,
            'slot': self.slot,
            'candidate_count': self.candidate_count,
            'email_sent': self.email_sent,
            'errors': self.errors,
        }


def format_subscription_time(created_at) -> str:
    """Render subscription created_at in Asia/Dhaka (RFC 3339-style offset)."""
    if created_at is None:
        return PLACEHOLDER
    aware = created_at
    if timezone.is_naive(aware):
        aware = timezone.make_aware(aware, timezone.get_current_timezone())
    local = aware.astimezone(BUSINESS_TZ)
    return local.isoformat(timespec='seconds')


def customer_email(customer) -> str:
    email = (getattr(customer.user, 'email', None) or '').strip()
    return email or PLACEHOLDER


def unassigned_active_subscriptions_queryset() -> QuerySet[CustomerSubscription]:
    """Active subscriptions whose customer has no operational delivery_sub_location."""
    return (
        CustomerSubscription.objects.filter(
            status=CustomerSubscription.Status.ACTIVE,
            customer__delivery_sub_location__isnull=True,
        )
        .select_related('customer', 'customer__user')
        .order_by('created_at', 'id')
    )


def build_unassigned_digest_rows(
    queryset: QuerySet[CustomerSubscription] | None = None,
) -> list[UnassignedDigestRow]:
    qs = queryset if queryset is not None else unassigned_active_subscriptions_queryset()
    rows: list[UnassignedDigestRow] = []
    for subscription in qs.iterator(chunk_size=200):
        customer = subscription.customer
        rows.append(
            UnassignedDigestRow(
                customer_id=customer.pk,
                name=customer_display_name(customer),
                phone=customer_phone(customer),
                subscription_time=format_subscription_time(subscription.created_at),
                email=customer_email(customer),
            )
        )
    return rows


def _format_admin_plain(rows: list[UnassignedDigestRow]) -> str:
    if not rows:
        return (
            'Unassigned delivery subscribers digest.\n\n'
            'No unassigned active subscribers in this run.'
        )
    lines = [
        'Unassigned delivery subscribers digest',
        f'Total: {len(rows)}',
        '',
        'Name | Phone | Subscription Time | Email',
        '-' * 72,
    ]
    for row in rows:
        lines.append(
            f'{row.name} | {row.phone} | {row.subscription_time} | {row.email}'
        )
        lines.append('')
        lines.append(f'Name: {row.name}')
        lines.append(f'Phone: {row.phone}')
        lines.append(f'Subscription Time: {row.subscription_time}')
        lines.append(f'Email: {row.email}')
        lines.append('-' * 32)
    return '\n'.join(lines)


def _format_admin_html(rows: list[UnassignedDigestRow]) -> str:
    if not rows:
        body = (
            '<p>Unassigned delivery subscribers digest.</p>'
            '<p>No unassigned active subscribers in this run.</p>'
        )
    else:
        rows_html = []
        for row in rows:
            rows_html.append(
                '<tr>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.name)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.phone)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.subscription_time)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.email)}</td>'
                '</tr>'
            )
        body = (
            f'<p>Unassigned delivery subscribers digest ({len(rows)} customers).</p>'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;width:100%;font-size:13px;">'
            '<thead><tr>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Name</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Phone</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Subscription Time</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Email</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody></table>'
        )
    return (
        f'<div style="font-family:Arial,sans-serif;color:{BRAND_DEEP_INK};'
        f'background:{BRAND_WARM_WHITE};padding:16px;">'
        f'<h2 style="color:{BRAND_DEEP_INK};border-bottom:3px solid {BRAND_YELLOW};'
        f'padding-bottom:8px;">{BRAND_NAME} — Unassigned Delivery Subscribers</h2>'
        f'{body}'
        '</div>'
    )


def notify_admins_unassigned_delivery_digest(
    *,
    rows: list[UnassignedDigestRow],
    dry_run: bool = False,
) -> bool:
    """
    Email verified admins the unassigned-delivery digest.

    Empty runs still send a short summary. Dry-run skips send.
    Returns True when an email was sent.
    """
    if dry_run:
        logger.info(
            'Dry-run: skipping unassigned delivery digest email candidate_count=%s',
            len(rows),
        )
        return False

    recipients = resolve_funding_admin_emails()
    if not recipients:
        logger.warning('No admin recipients for unassigned delivery digest; skipping.')
        return False

    count = len(rows)
    if count:
        subject = f'[BeFood] Unassigned delivery subscribers ({count})'
    else:
        subject = '[BeFood] Unassigned delivery subscribers (0) — none pending'

    text_body = _format_admin_plain(rows)
    html_body = _format_admin_html(rows)
    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
    return True


def run_unassigned_delivery_digest(
    *,
    dry_run: bool = False,
    slot: str | None = None,
) -> UnassignedDigestRunResult:
    """
    Query unassigned active subscribers and email admins.

    Send failures are logged and counted; they do not raise into callers.
    """
    normalized_slot = (slot or '').strip().lower() or None
    if normalized_slot is not None and normalized_slot not in VALID_SLOTS:
        logger.warning('Unknown digest slot=%s; continuing without slot label', slot)
        normalized_slot = None

    result = UnassignedDigestRunResult(dry_run=dry_run, slot=normalized_slot)
    try:
        result.rows = build_unassigned_digest_rows()
        result.candidate_count = len(result.rows)
    except Exception:
        result.errors += 1
        logger.exception('Unassigned delivery digest query failed')
        return result

    try:
        result.email_sent = notify_admins_unassigned_delivery_digest(
            rows=result.rows,
            dry_run=dry_run,
        )
    except Exception:
        result.errors += 1
        logger.exception('Unassigned delivery digest email failed')

    return result
