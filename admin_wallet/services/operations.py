"""Manual deposit, withdrawal, expense, and adjustment operations."""

from __future__ import annotations

from typing import Optional

from django.db import transaction

from admin_wallet.models import AdminWalletAuditLog, AdminWalletTransaction
from admin_wallet.services.ledger import (
    AdminWalletError,
    credit_admin_wallet,
    debit_admin_wallet,
    get_or_create_platform_wallet,
    validate_amount,
)


def _require_reason(reason: str) -> str:
    value = (reason or '').strip()
    if not value:
        raise AdminWalletError('Reason is required.', code='REASON_REQUIRED')
    return value


def _write_audit_once(
    *,
    action: str,
    actor_admin,
    amount,
    previous_balance,
    new_balance,
    reason: str,
    transaction_obj: AdminWalletTransaction,
    metadata: Optional[dict] = None,
) -> None:
    if AdminWalletAuditLog.objects.filter(transaction=transaction_obj).exists():
        return
    AdminWalletAuditLog.objects.create(
        actor_admin=actor_admin,
        action=action,
        amount=amount,
        previous_balance=previous_balance,
        new_balance=new_balance,
        reason=reason or '',
        transaction=transaction_obj,
        metadata=metadata or {},
    )


@transaction.atomic
def manual_deposit(
    amount,
    *,
    reason: str,
    note: str = '',
    actor_admin=None,
    idempotency_key: Optional[str] = None,
) -> AdminWalletTransaction:
    reason = _require_reason(reason)
    amount = validate_amount(amount)
    wallet = get_or_create_platform_wallet()

    txn = credit_admin_wallet(
        amount,
        type=AdminWalletTransaction.Type.MANUAL_DEPOSIT,
        method=AdminWalletTransaction.Method.MANUAL,
        status=AdminWalletTransaction.Status.COMPLETED,
        note=note,
        reason=reason,
        source='Manual Deposit',
        reference='Added by Admin',
        idempotency_key=idempotency_key,
        actor_admin=actor_admin,
        wallet=wallet,
    )
    _write_audit_once(
        action=AdminWalletAuditLog.Action.MANUAL_DEPOSIT,
        actor_admin=actor_admin,
        amount=amount,
        previous_balance=txn.balance_after - amount,
        new_balance=txn.balance_after,
        reason=reason,
        transaction_obj=txn,
    )
    return txn


@transaction.atomic
def withdraw(
    amount,
    *,
    reason: str,
    note: str = '',
    actor_admin=None,
    idempotency_key: Optional[str] = None,
) -> AdminWalletTransaction:
    reason = _require_reason(reason)
    amount = validate_amount(amount)
    wallet = get_or_create_platform_wallet()

    txn = debit_admin_wallet(
        amount,
        type=AdminWalletTransaction.Type.WITHDRAWAL,
        method=AdminWalletTransaction.Method.MANUAL,
        status=AdminWalletTransaction.Status.COMPLETED,
        note=note,
        reason=reason,
        source='Withdrawal',
        reference=reason,
        idempotency_key=idempotency_key,
        actor_admin=actor_admin,
        wallet=wallet,
    )
    _write_audit_once(
        action=AdminWalletAuditLog.Action.WITHDRAWAL,
        actor_admin=actor_admin,
        amount=amount,
        previous_balance=txn.balance_after + amount,
        new_balance=txn.balance_after,
        reason=reason,
        transaction_obj=txn,
    )
    return txn


@transaction.atomic
def post_expense(
    amount,
    *,
    type: str,
    reason: str,
    note: str = '',
    actor_admin=None,
    order=None,
    customer=None,
    idempotency_key: Optional[str] = None,
    reference: str = '',
) -> AdminWalletTransaction:
    reason = _require_reason(reason)
    if type not in AdminWalletTransaction.EXPENSE_TYPES:
        raise AdminWalletError(
            f'Type {type} is not an allowed expense type.',
            code='INVALID_EXPENSE_TYPE',
        )
    amount = validate_amount(amount)
    wallet = get_or_create_platform_wallet()

    txn = debit_admin_wallet(
        amount,
        type=type,
        method=AdminWalletTransaction.Method.MANUAL,
        status=AdminWalletTransaction.Status.COMPLETED,
        note=note,
        reason=reason,
        source=type.replace('_', ' ').title(),
        reference=reference or reason,
        idempotency_key=idempotency_key,
        actor_admin=actor_admin,
        order=order,
        customer=customer,
        wallet=wallet,
    )
    _write_audit_once(
        action=AdminWalletAuditLog.Action.EXPENSE,
        actor_admin=actor_admin,
        amount=amount,
        previous_balance=txn.balance_after + amount,
        new_balance=txn.balance_after,
        reason=reason,
        transaction_obj=txn,
        metadata={'expense_type': type},
    )
    return txn


@transaction.atomic
def adjust_admin_wallet(
    amount,
    *,
    direction: str,
    reason: str,
    note: str = '',
    actor_admin=None,
    idempotency_key: Optional[str] = None,
) -> AdminWalletTransaction:
    """Restricted balance adjustment (credit=adjustment, debit=manual_adjustment)."""
    reason = _require_reason(reason)
    amount = validate_amount(amount)
    wallet = get_or_create_platform_wallet()

    if direction == AdminWalletTransaction.Direction.CREDIT:
        txn = credit_admin_wallet(
            amount,
            type=AdminWalletTransaction.Type.ADJUSTMENT,
            method=AdminWalletTransaction.Method.MANUAL,
            status=AdminWalletTransaction.Status.COMPLETED,
            note=note,
            reason=reason,
            source='Adjustment',
            reference=reason,
            idempotency_key=idempotency_key,
            actor_admin=actor_admin,
            wallet=wallet,
        )
        previous_balance = txn.balance_after - amount
    elif direction == AdminWalletTransaction.Direction.DEBIT:
        txn = debit_admin_wallet(
            amount,
            type=AdminWalletTransaction.Type.MANUAL_ADJUSTMENT,
            method=AdminWalletTransaction.Method.MANUAL,
            status=AdminWalletTransaction.Status.COMPLETED,
            note=note,
            reason=reason,
            source='Manual Adjustment',
            reference=reason,
            idempotency_key=idempotency_key,
            actor_admin=actor_admin,
            wallet=wallet,
        )
        previous_balance = txn.balance_after + amount
    else:
        raise AdminWalletError(
            'Direction must be credit or debit.',
            code='INVALID_DIRECTION',
        )

    _write_audit_once(
        action=AdminWalletAuditLog.Action.ADJUSTMENT,
        actor_admin=actor_admin,
        amount=amount,
        previous_balance=previous_balance,
        new_balance=txn.balance_after,
        reason=reason,
        transaction_obj=txn,
        metadata={'direction': direction},
    )
    return txn
