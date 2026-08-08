"""Admin Wallet ledger — singleton platform wallet credit/debit primitives."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db import IntegrityError, transaction

from admin_wallet.models import AdminWallet, AdminWalletTransaction

MAX_AMOUNT = Decimal('10000000.00')
MIN_AMOUNT = Decimal('0.01')


class AdminWalletError(Exception):
    """Base error for admin wallet domain operations."""

    def __init__(self, message: str, *, code: str = 'ADMIN_WALLET_ERROR'):
        super().__init__(message)
        self.code = code


class InvalidAmountError(AdminWalletError):
    def __init__(self, message: str = 'Invalid amount.'):
        super().__init__(message, code='INVALID_AMOUNT')


class InsufficientFundsError(AdminWalletError):
    def __init__(self, message: str = 'Insufficient admin wallet balance.'):
        super().__init__(message, code='INSUFFICIENT_FUNDS')


class WalletFrozenError(AdminWalletError):
    def __init__(self, message: str = 'Admin wallet is frozen.'):
        super().__init__(message, code='WALLET_FROZEN')


class IdempotencyConflictError(AdminWalletError):
    def __init__(self, message: str = 'Idempotency key conflict.'):
        super().__init__(message, code='IDEMPOTENCY_CONFLICT')


def validate_amount(amount) -> Decimal:
    try:
        value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidAmountError('Amount must be a valid decimal number.') from exc

    if value <= 0:
        raise InvalidAmountError('Amount must be greater than zero.')
    if value < MIN_AMOUNT:
        raise InvalidAmountError(f'Amount must be at least {MIN_AMOUNT}.')
    if value > MAX_AMOUNT:
        raise InvalidAmountError(f'Amount must not exceed {MAX_AMOUNT}.')
    if value.as_tuple().exponent < -2:
        raise InvalidAmountError('Amount must have at most 2 decimal places.')

    return value.quantize(Decimal('0.01'))


def get_or_create_platform_wallet() -> AdminWallet:
    wallet, _ = AdminWallet.objects.get_or_create(
        code=AdminWallet.PLATFORM_CODE,
        defaults={
            'balance': Decimal('0.00'),
            'currency': 'BDT',
            'status': AdminWallet.Status.ACTIVE,
        },
    )
    return wallet


def _ensure_active(wallet: AdminWallet) -> None:
    if wallet.status == AdminWallet.Status.FROZEN:
        raise WalletFrozenError()


def _find_idempotent_txn(
    wallet: AdminWallet,
    idempotency_key: Optional[str],
    amount: Decimal,
) -> Optional[AdminWalletTransaction]:
    if not idempotency_key:
        return None
    existing = (
        AdminWalletTransaction.objects.filter(
            wallet=wallet,
            idempotency_key=idempotency_key,
        )
        .order_by('created_at')
        .first()
    )
    if existing is None:
        return None
    if existing.amount != amount:
        raise IdempotencyConflictError(
            'Idempotency key was already used with a different amount.'
        )
    return existing


def _apply_lifetime_counters(
    wallet: AdminWallet,
    *,
    direction: str,
    txn_type: str,
    amount: Decimal,
) -> list[str]:
    """Mutate denormalized counters on locked wallet; return update_fields extras."""
    fields: list[str] = []
    if direction == AdminWalletTransaction.Direction.CREDIT:
        if txn_type == AdminWalletTransaction.Type.INVENTORY_PURCHASE_REVERSAL:
            # Compensating credit for cancelled inventory purchase — not income.
            current = wallet.total_expenses or Decimal('0.00')
            wallet.total_expenses = max(Decimal('0.00'), current - amount)
            fields.append('total_expenses')
        else:
            wallet.total_received = (wallet.total_received or Decimal('0.00')) + amount
            fields.append('total_received')
            if txn_type == AdminWalletTransaction.Type.MANUAL_DEPOSIT:
                wallet.total_manual_added = (
                    wallet.total_manual_added or Decimal('0.00')
                ) + amount
                fields.append('total_manual_added')
            if txn_type == AdminWalletTransaction.Type.CUSTOMER_FUNDING:
                wallet.total_customer_funding = (
                    wallet.total_customer_funding or Decimal('0.00')
                ) + amount
                fields.append('total_customer_funding')
            # Legacy: historical meal cash credits only (new meal path does not cash-credit).
            if txn_type == AdminWalletTransaction.Type.CUSTOMER_PAYMENT:
                wallet.total_customer_payments = (
                    wallet.total_customer_payments or Decimal('0.00')
                ) + amount
                fields.append('total_customer_payments')
    else:
        if txn_type == AdminWalletTransaction.Type.WITHDRAWAL:
            wallet.total_withdrawn = (wallet.total_withdrawn or Decimal('0.00')) + amount
            fields.append('total_withdrawn')
        elif txn_type == AdminWalletTransaction.Type.CUSTOMER_WITHDRAW:
            wallet.total_customer_withdrawals = (
                wallet.total_customer_withdrawals or Decimal('0.00')
            ) + amount
            fields.append('total_customer_withdrawals')
        elif txn_type in AdminWalletTransaction.EXPENSE_TYPES:
            wallet.total_expenses = (wallet.total_expenses or Decimal('0.00')) + amount
            fields.append('total_expenses')
    return fields


def _create_txn_kwargs(
    *,
    type: str,
    direction: str,
    amount: Decimal,
    balance_after: Decimal,
    status: str,
    method: str,
    note: str,
    reason: str,
    source: str,
    reference: str,
    external_ref: str,
    idempotency_key: Optional[str],
    metadata: Optional[dict],
    order=None,
    order_delivery=None,
    customer=None,
    actor_admin=None,
    customer_wallet_transaction=None,
) -> dict:
    return {
        'type': type,
        'direction': direction,
        'amount': amount,
        'balance_after': balance_after,
        'status': status,
        'method': method,
        'note': note or '',
        'reason': reason or '',
        'source': source or '',
        'reference': reference or '',
        'external_ref': external_ref or '',
        'idempotency_key': idempotency_key or None,
        'metadata': metadata or {},
        'order': order,
        'order_delivery': order_delivery,
        'customer': customer,
        'actor_admin': actor_admin,
        'customer_wallet_transaction': customer_wallet_transaction,
    }


@transaction.atomic
def credit_admin_wallet(
    amount,
    *,
    type: str = AdminWalletTransaction.Type.OTHER_INCOME,
    method: str = AdminWalletTransaction.Method.MANUAL,
    status: str = AdminWalletTransaction.Status.COMPLETED,
    note: str = '',
    reason: str = '',
    source: str = '',
    reference: str = '',
    external_ref: str = '',
    idempotency_key: Optional[str] = None,
    metadata: Optional[dict] = None,
    order=None,
    order_delivery=None,
    customer=None,
    actor_admin=None,
    customer_wallet_transaction=None,
    wallet: Optional[AdminWallet] = None,
) -> AdminWalletTransaction:
    """Credit platform wallet and append a ledger row (concurrency-safe)."""
    if type not in AdminWalletTransaction.CREDIT_TYPES:
        raise AdminWalletError(
            f'Type {type} is not a credit type.',
            code='INVALID_TRANSACTION_TYPE',
        )

    amount = validate_amount(amount)
    platform = wallet or get_or_create_platform_wallet()
    locked = AdminWallet.objects.select_for_update().get(pk=platform.pk)
    _ensure_active(locked)

    existing = _find_idempotent_txn(locked, idempotency_key, amount)
    if existing is not None:
        return existing

    # select_for_update serializes writers; idempotency check above covers retries.
    new_balance = locked.balance + amount
    locked.balance = new_balance
    counter_fields = _apply_lifetime_counters(
        locked,
        direction=AdminWalletTransaction.Direction.CREDIT,
        txn_type=type,
        amount=amount,
    )
    locked.save(update_fields=['balance', 'updated_at', *counter_fields])

    try:
        txn = AdminWalletTransaction.objects.create(
            wallet=locked,
            **_create_txn_kwargs(
                type=type,
                direction=AdminWalletTransaction.Direction.CREDIT,
                amount=amount,
                balance_after=new_balance,
                status=status,
                method=method,
                note=note,
                reason=reason,
                source=source,
                reference=reference,
                external_ref=external_ref,
                idempotency_key=idempotency_key,
                metadata=metadata,
                order=order,
                order_delivery=order_delivery,
                customer=customer,
                actor_admin=actor_admin,
                customer_wallet_transaction=customer_wallet_transaction,
            ),
        )
    except IntegrityError as exc:
        raced = _find_idempotent_txn(locked, idempotency_key, amount)
        if raced is not None:
            raise IdempotencyConflictError(
                'Concurrent idempotent credit; retry to load existing row.'
            ) from exc
        raise

    if wallet is not None:
        wallet.balance = new_balance
    return txn


@transaction.atomic
def debit_admin_wallet(
    amount,
    *,
    type: str = AdminWalletTransaction.Type.WITHDRAWAL,
    method: str = AdminWalletTransaction.Method.MANUAL,
    status: str = AdminWalletTransaction.Status.COMPLETED,
    note: str = '',
    reason: str = '',
    source: str = '',
    reference: str = '',
    external_ref: str = '',
    idempotency_key: Optional[str] = None,
    metadata: Optional[dict] = None,
    order=None,
    order_delivery=None,
    customer=None,
    actor_admin=None,
    customer_wallet_transaction=None,
    wallet: Optional[AdminWallet] = None,
) -> AdminWalletTransaction:
    """Debit platform wallet and append a ledger row (concurrency-safe)."""
    if type not in AdminWalletTransaction.DEBIT_TYPES:
        raise AdminWalletError(
            f'Type {type} is not a debit type.',
            code='INVALID_TRANSACTION_TYPE',
        )

    amount = validate_amount(amount)
    platform = wallet or get_or_create_platform_wallet()
    locked = AdminWallet.objects.select_for_update().get(pk=platform.pk)
    _ensure_active(locked)

    existing = _find_idempotent_txn(locked, idempotency_key, amount)
    if existing is not None:
        return existing

    if amount > locked.balance:
        raise InsufficientFundsError()

    new_balance = locked.balance - amount
    locked.balance = new_balance
    counter_fields = _apply_lifetime_counters(
        locked,
        direction=AdminWalletTransaction.Direction.DEBIT,
        txn_type=type,
        amount=amount,
    )
    locked.save(update_fields=['balance', 'updated_at', *counter_fields])

    try:
        txn = AdminWalletTransaction.objects.create(
            wallet=locked,
            **_create_txn_kwargs(
                type=type,
                direction=AdminWalletTransaction.Direction.DEBIT,
                amount=amount,
                balance_after=new_balance,
                status=status,
                method=method,
                note=note,
                reason=reason,
                source=source,
                reference=reference,
                external_ref=external_ref,
                idempotency_key=idempotency_key,
                metadata=metadata,
                order=order,
                order_delivery=order_delivery,
                customer=customer,
                actor_admin=actor_admin,
                customer_wallet_transaction=customer_wallet_transaction,
            ),
        )
    except IntegrityError:
        raise AdminWalletError(
            'Concurrent ledger write conflict; retry.',
            code='LEDGER_RACE',
        ) from None

    if wallet is not None:
        wallet.balance = new_balance
    return txn
