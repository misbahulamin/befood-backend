"""Reusable transaction invoice identity and email context builders."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.utils import timezone

from wallet.models import WalletTransaction

# Metadata keys written at approve time (stable contract for templates/retries).
META_PREVIOUS_BALANCE = 'previous_balance'
META_NOTICE_SCHEDULED = 'customer_approval_notice_scheduled'

INVOICE_TYPE_WALLET_RECHARGE = 'wallet_recharge'


def generate_recharge_invoice_number(txn: WalletTransaction) -> str:
    """
    Stable unique invoice number derived from the transaction public_id.

    Format: INV-WR-{YYYYMMDD}-{12 hex chars from public_id}
    Future types can use INV-<TYPE>-... via a shared helper.
    """
    pid = str(getattr(txn, 'public_id', '') or '').replace('-', '')
    short = (pid[:12] or 'UNKNOWN').upper()
    stamp = timezone.localdate().strftime('%Y%m%d')
    return f'INV-WR-{stamp}-{short}'


def ensure_invoice_for_recharge(
    txn: WalletTransaction,
    *,
    previous_balance: Optional[Decimal] = None,
) -> WalletTransaction:
    """
    Assign invoice_number (once) and optional previous_balance snapshot.

    Idempotent: existing invoice_number is kept. Caller should hold a row lock
    when writing during approve.
    """
    meta = dict(txn.metadata or {})
    dirty = False

    if not txn.invoice_number:
        txn.invoice_number = generate_recharge_invoice_number(txn)
        dirty = True

    if previous_balance is not None and META_PREVIOUS_BALANCE not in meta:
        meta[META_PREVIOUS_BALANCE] = f'{Decimal(previous_balance):.2f}'
        dirty = True

    if not meta.get(META_NOTICE_SCHEDULED):
        meta[META_NOTICE_SCHEDULED] = True
        dirty = True

    if dirty:
        txn.metadata = meta
        txn.save(update_fields=['invoice_number', 'metadata', 'updated_at'])

    return txn


def _customer_display_name(user) -> str:
    parts = [
        (getattr(user, 'first_name', None) or '').strip(),
        (getattr(user, 'last_name', None) or '').strip(),
    ]
    name = ' '.join(p for p in parts if p)
    if name:
        return name
    return (getattr(user, 'email', None) or getattr(user, 'username', None) or '').strip()


def _format_money(value: Decimal | str | None) -> str:
    if value is None or value == '':
        return '0.00'
    return f'{Decimal(value):.2f}'


def build_invoice_context(txn: WalletTransaction) -> dict[str, Any]:
    """
    Stable invoice context keys for branded email templates.

    Shared keys (reusable for future invoice types):
      invoice_type, invoice_number, invoice_status, invoice_date,
      customer_name, customer_email, customer_phone,
      amount, previous_balance, updated_balance, currency_symbol,
      payment_method, payment_reference, line_title, line_description

    Recharge-specific extras stay under the same keys where possible.
    """
    wallet = txn.wallet
    customer = wallet.customer
    user = customer.user
    meta = txn.metadata or {}

    previous = meta.get(META_PREVIOUS_BALANCE)
    if previous is None and txn.balance_after is not None:
        previous = txn.balance_after - txn.amount

    updated = txn.balance_after
    reviewed_at = txn.reviewed_at or txn.updated_at or timezone.now()

    return {
        'invoice_type': INVOICE_TYPE_WALLET_RECHARGE,
        'invoice_number': txn.invoice_number or '',
        'invoice_status': 'Approved / Completed',
        'invoice_date': reviewed_at,
        'invoice_date_display': timezone.localtime(reviewed_at).strftime(
            '%Y-%m-%d %H:%M %Z'
        ),
        'customer_name': _customer_display_name(user),
        'customer_email': (getattr(user, 'email', None) or '').strip(),
        'customer_phone': (getattr(customer, 'phone', None) or '').strip(),
        'amount': _format_money(txn.amount),
        'previous_balance': _format_money(previous),
        'updated_balance': _format_money(updated),
        'currency_symbol': '৳',
        'payment_method': (txn.method or '').strip(),
        'payment_reference': (txn.external_ref or '').strip(),
        'transaction_public_id': str(txn.public_id),
        'line_title': 'Wallet recharge',
        'line_description': 'Customer wallet top-up (manual verification)',
        'wallet_transaction': txn,
    }
