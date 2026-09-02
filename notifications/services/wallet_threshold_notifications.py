"""Best-effort customer push/email and admin summary for wallet thresholds."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from notifications.services.device_service import get_user_device_tokens
from notifications.services.fcm_service import FCMNotConfiguredError, send_to_tokens
from orders.services.wallet_balance_thresholds import AffectedUserRow
from user_management.services.email_branding import (
    BRAND_DEEP_INK,
    BRAND_NAME,
    BRAND_WARM_WHITE,
    BRAND_YELLOW,
    build_brand_email_context,
)
from wallet.services.funding_notifications import resolve_funding_admin_emails

logger = logging.getLogger(__name__)


def _send_customer_push(*, user, title: str, body: str, data: dict) -> None:
    tokens = get_user_device_tokens(user)
    if not tokens:
        logger.info(
            'Skipping wallet-threshold push: no tokens user_id=%s type=%s',
            getattr(user, 'pk', None),
            data.get('type'),
        )
        return
    send_to_tokens(tokens, title, body, data)


def _send_customer_email(*, user, subject_template: str, text_template: str, html_template: str, extra: dict) -> None:
    email_addr = (getattr(user, 'email', None) or '').strip()
    if not email_addr:
        logger.info(
            'Skipping wallet-threshold email: no address user_id=%s',
            getattr(user, 'pk', None),
        )
        return
    context = build_brand_email_context(user, extra=extra)
    subject = render_to_string(subject_template, context).strip()
    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)
    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [email_addr],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)


def notify_customer_low_balance_reminder(
    customer,
    *,
    balance: Decimal,
    reminder_threshold: Decimal,
    meal_stop_threshold: Decimal,
) -> None:
    """Push + email low-balance reminder. Never raises into callers."""
    try:
        user = customer.user
        title = 'Wallet balance is low'
        body = (
            f'Your balance is ৳{balance:.2f}. Please recharge. '
            f'If balance goes below ৳{meal_stop_threshold:.2f}, meal service will stop.'
        )
        data = {
            'type': 'wallet_low_balance',
            'balance': f'{balance:.2f}',
            'reminder_threshold': f'{reminder_threshold:.2f}',
            'meal_stop_threshold': f'{meal_stop_threshold:.2f}',
        }
        try:
            _send_customer_push(user=user, title=title, body=body, data=data)
        except FCMNotConfiguredError:
            logger.info('FCM not configured; skipped low-balance push user_id=%s', user.pk)
        except Exception:
            logger.exception('Low-balance push failed user_id=%s', user.pk)

        try:
            _send_customer_email(
                user=user,
                subject_template='emails/wallet_low_balance_reminder_subject.txt',
                text_template='emails/wallet_low_balance_reminder_email.txt',
                html_template='emails/wallet_low_balance_reminder_email.html',
                extra={
                    'balance': f'{balance:.2f}',
                    'reminder_threshold': f'{reminder_threshold:.2f}',
                    'meal_stop_threshold': f'{meal_stop_threshold:.2f}',
                },
            )
        except Exception:
            logger.exception('Low-balance email failed user_id=%s', user.pk)
    except Exception:
        logger.exception(
            'Low-balance reminder failed customer_id=%s',
            getattr(customer, 'pk', None),
        )


def notify_customer_meal_stop(
    customer,
    *,
    balance: Decimal,
    meal_stop_threshold: Decimal,
) -> None:
    """Push + email meal-stop notice. Never raises into callers."""
    try:
        user = customer.user
        title = 'Meal service stopped'
        body = (
            f'Your wallet balance is ৳{balance:.2f} (below ৳{meal_stop_threshold:.2f}). '
            'Meal delivery is paused until you recharge.'
        )
        data = {
            'type': 'wallet_meal_stop',
            'balance': f'{balance:.2f}',
            'meal_stop_threshold': f'{meal_stop_threshold:.2f}',
        }
        try:
            _send_customer_push(user=user, title=title, body=body, data=data)
        except FCMNotConfiguredError:
            logger.info('FCM not configured; skipped meal-stop push user_id=%s', user.pk)
        except Exception:
            logger.exception('Meal-stop push failed user_id=%s', user.pk)

        try:
            _send_customer_email(
                user=user,
                subject_template='emails/wallet_meal_stop_subject.txt',
                text_template='emails/wallet_meal_stop_email.txt',
                html_template='emails/wallet_meal_stop_email.html',
                extra={
                    'balance': f'{balance:.2f}',
                    'meal_stop_threshold': f'{meal_stop_threshold:.2f}',
                },
            )
        except Exception:
            logger.exception('Meal-stop email failed user_id=%s', user.pk)
    except Exception:
        logger.exception(
            'Meal-stop notify failed customer_id=%s',
            getattr(customer, 'pk', None),
        )


def _format_admin_plain(affected: list[AffectedUserRow], business_date: date) -> str:
    if not affected:
        return (
            f'Low balance wallet report for {business_date.isoformat()}.\n\n'
            'No low-balance or meal-stopped users in this run.'
        )
    lines = [
        f'Low Balance Users Report ({business_date.isoformat()})',
        f'Total affected: {len(affected)}',
        '',
        'Name | Phone | Package | Current Balance | Address | Status',
        '-' * 72,
    ]
    for row in affected:
        lines.append(
            f'{row.name} | {row.phone} | {row.package_name} | '
            f'{row.balance:.2f} TK | {row.address} | {row.status}'
        )
        lines.append('')
        lines.append(f'Name: {row.name}')
        lines.append(f'Phone: {row.phone}')
        lines.append(f'Package: {row.package_name}')
        lines.append(f'Current Balance: {row.balance:.2f} TK')
        lines.append(f'Address: {row.address}')
        lines.append(f'Status: {row.status}')
        lines.append('-' * 32)
    return '\n'.join(lines)


def _format_admin_html(affected: list[AffectedUserRow], business_date: date) -> str:
    if not affected:
        body = (
            f'<p>Low balance wallet report for <strong>{escape(business_date.isoformat())}</strong>.</p>'
            '<p>No low-balance or meal-stopped users in this run.</p>'
        )
    else:
        rows_html = []
        for row in affected:
            rows_html.append(
                '<tr>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.name)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.phone)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.package_name)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;text-align:right;">'
                f'{escape(f"{row.balance:.2f}")} TK</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.address)}</td>'
                f'<td style="border:1px solid #ccc;padding:8px;">{escape(row.status)}</td>'
                '</tr>'
            )
        body = (
            f'<p>Low Balance Users Report for <strong>{escape(business_date.isoformat())}</strong> '
            f'({len(affected)} users).</p>'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;width:100%;font-size:13px;">'
            '<thead><tr>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Name</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Phone</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Package</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:right;">Current Balance</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Address</th>'
            '<th style="border:1px solid #ccc;padding:8px;background:#f5f5f5;text-align:left;">Status</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody></table>'
        )
    return (
        f'<div style="font-family:Arial,sans-serif;color:{BRAND_DEEP_INK};'
        f'background:{BRAND_WARM_WHITE};padding:16px;">'
        f'<h2 style="color:{BRAND_DEEP_INK};border-bottom:3px solid {BRAND_YELLOW};'
        f'padding-bottom:8px;">{BRAND_NAME} — Low Balance Report</h2>'
        f'{body}'
        '</div>'
    )


def notify_admins_low_balance_summary(
    *,
    affected: list[AffectedUserRow],
    business_date: date,
) -> None:
    """
    Email verified admins a structured low-balance report.

    Empty runs still send a short “no low-balance users” summary so ops know
    the cron executed successfully.
    """
    recipients = resolve_funding_admin_emails()
    if not recipients:
        logger.warning('No admin recipients for low-balance summary; skipping.')
        return
    subject = f'[Befood] Low balance users report ({business_date.isoformat()})'
    text_body = _format_admin_plain(affected, business_date)
    html_body = _format_admin_html(affected, business_date)
    message = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
