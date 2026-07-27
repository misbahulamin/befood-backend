"""Wallet ledger services — credit/debit, funding, and gateway completion hooks."""

from decimal import Decimal, InvalidOperation
from typing import Optional

from django.conf import settings
from django.db import transaction

from wallet.models import Wallet, WalletTransaction

# Maximum single funding amount (recharge / withdraw).
MAX_FUNDING_AMOUNT = Decimal('100000.00')
MIN_FUNDING_AMOUNT = Decimal('0.01')


class WalletError(Exception):
    """Base error for wallet domain operations."""


class InvalidAmountError(WalletError):
    pass


class InsufficientFundsError(WalletError):
    pass


class WalletFrozenError(WalletError):
    pass


class ManualFundingDisabledError(WalletError):
    pass


class IdempotencyConflictError(WalletError):
    pass


class PendingTransactionError(WalletError):
    pass


def validate_amount(amount) -> Decimal:
    """Validate a monetary amount: positive, ≤2 decimal places, within max cap."""
    try:
        value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidAmountError('Amount must be a valid decimal number.') from exc

    if value <= 0:
        raise InvalidAmountError('Amount must be greater than zero.')
    if value < MIN_FUNDING_AMOUNT:
        raise InvalidAmountError(f'Amount must be at least {MIN_FUNDING_AMOUNT}.')
    if value > MAX_FUNDING_AMOUNT:
        raise InvalidAmountError(f'Amount must not exceed {MAX_FUNDING_AMOUNT}.')
    if value.as_tuple().exponent < -2:
        raise InvalidAmountError('Amount must have at most 2 decimal places.')

    return value.quantize(Decimal('0.01'))


def get_or_create_wallet(customer_profile) -> Wallet:
    """Return the customer's wallet, creating an active zero-balance wallet if needed."""
    wallet, _ = Wallet.objects.get_or_create(
        customer=customer_profile,
        defaults={
            'balance': Decimal('0.00'),
            'currency': 'BDT',
            'status': Wallet.Status.ACTIVE,
        },
    )
    return wallet


def _ensure_active(wallet: Wallet) -> None:
    if wallet.status == Wallet.Status.FROZEN:
        raise WalletFrozenError('Wallet is frozen and cannot accept balance changes.')


def _manual_funding_enabled() -> bool:
    return bool(getattr(settings, 'WALLET_MANUAL_FUNDING_ENABLED', True))


@transaction.atomic
def credit_wallet(
    wallet: Wallet,
    amount,
    *,
    type: str = WalletTransaction.Type.RECHARGE,
    method: str = WalletTransaction.Method.MANUAL,
    status: str = WalletTransaction.Status.COMPLETED,
    note: str = '',
    external_ref: str = '',
    idempotency_key: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> WalletTransaction:
    """Credit wallet balance and append a ledger row (concurrency-safe)."""
    amount = validate_amount(amount)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
    _ensure_active(locked)

    new_balance = locked.balance + amount
    locked.balance = new_balance
    locked.save(update_fields=['balance', 'updated_at'])

    txn = WalletTransaction.objects.create(
        wallet=locked,
        type=type,
        direction=WalletTransaction.Direction.CREDIT,
        amount=amount,
        balance_after=new_balance,
        status=status,
        method=method,
        note=note or '',
        external_ref=external_ref or '',
        idempotency_key=idempotency_key or None,
        metadata=metadata or {},
    )
    wallet.balance = new_balance
    return txn


@transaction.atomic
def debit_wallet(
    wallet: Wallet,
    amount,
    *,
    type: str = WalletTransaction.Type.WITHDRAW,
    method: str = WalletTransaction.Method.MANUAL,
    status: str = WalletTransaction.Status.COMPLETED,
    note: str = '',
    external_ref: str = '',
    idempotency_key: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> WalletTransaction:
    """Debit wallet balance and append a ledger row (concurrency-safe)."""
    amount = validate_amount(amount)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
    _ensure_active(locked)

    if amount > locked.balance:
        raise InsufficientFundsError('Insufficient wallet balance.')

    new_balance = locked.balance - amount
    locked.balance = new_balance
    locked.save(update_fields=['balance', 'updated_at'])

    txn = WalletTransaction.objects.create(
        wallet=locked,
        type=type,
        direction=WalletTransaction.Direction.DEBIT,
        amount=amount,
        balance_after=new_balance,
        status=status,
        method=method,
        note=note or '',
        external_ref=external_ref or '',
        idempotency_key=idempotency_key or None,
        metadata=metadata or {},
    )
    wallet.balance = new_balance
    return txn


def _find_idempotent_txn(wallet: Wallet, idempotency_key: Optional[str], amount: Decimal):
    if not idempotency_key:
        return None
    existing = (
        WalletTransaction.objects.filter(wallet=wallet, idempotency_key=idempotency_key)
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


@transaction.atomic
def recharge_wallet(
    customer_profile,
    amount,
    *,
    note: str = '',
    idempotency_key: Optional[str] = None,
) -> tuple[Wallet, WalletTransaction]:
    """Manual recharge: immediate completed credit. Gateway methods are not accepted here."""
    if not _manual_funding_enabled():
        raise ManualFundingDisabledError('Manual wallet funding is currently disabled.')

    amount = validate_amount(amount)
    wallet = get_or_create_wallet(customer_profile)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)

    existing = _find_idempotent_txn(locked, idempotency_key, amount)
    if existing is not None:
        locked.refresh_from_db()
        return locked, existing

    txn = credit_wallet(
        locked,
        amount,
        type=WalletTransaction.Type.RECHARGE,
        method=WalletTransaction.Method.MANUAL,
        status=WalletTransaction.Status.COMPLETED,
        note=note,
        idempotency_key=idempotency_key,
    )
    locked.refresh_from_db()
    return locked, txn


@transaction.atomic
def withdraw_wallet(
    customer_profile,
    amount,
    *,
    note: str = '',
    idempotency_key: Optional[str] = None,
) -> tuple[Wallet, WalletTransaction]:
    """Manual withdraw: immediate completed debit. Real payout rails come later."""
    if not _manual_funding_enabled():
        raise ManualFundingDisabledError('Manual wallet funding is currently disabled.')

    amount = validate_amount(amount)
    wallet = get_or_create_wallet(customer_profile)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)

    existing = _find_idempotent_txn(locked, idempotency_key, amount)
    if existing is not None:
        locked.refresh_from_db()
        return locked, existing

    txn = debit_wallet(
        locked,
        amount,
        type=WalletTransaction.Type.WITHDRAW,
        method=WalletTransaction.Method.MANUAL,
        status=WalletTransaction.Status.COMPLETED,
        note=note,
        idempotency_key=idempotency_key,
    )
    locked.refresh_from_db()
    return locked, txn


@transaction.atomic
def complete_pending_credit(txn: WalletTransaction) -> WalletTransaction:
    """
    Gateway seam: move a pending credit transaction to completed and apply balance.

    Reserved for future bKash/Nagad webhook handlers. Do not call from customer APIs yet.
    """
    locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
    if locked_txn.status != WalletTransaction.Status.PENDING:
        raise PendingTransactionError('Only pending transactions can be completed.')
    if locked_txn.direction != WalletTransaction.Direction.CREDIT:
        raise PendingTransactionError('complete_pending_credit requires a credit transaction.')

    wallet = Wallet.objects.select_for_update().get(pk=locked_txn.wallet_id)
    _ensure_active(wallet)

    new_balance = wallet.balance + locked_txn.amount
    wallet.balance = new_balance
    wallet.save(update_fields=['balance', 'updated_at'])

    locked_txn.status = WalletTransaction.Status.COMPLETED
    locked_txn.balance_after = new_balance
    locked_txn.save(update_fields=['status', 'balance_after', 'updated_at'])
    return locked_txn


@transaction.atomic
def fail_pending(txn: WalletTransaction, *, note: str = '') -> WalletTransaction:
    """
    Gateway seam: mark a pending transaction as failed without changing balance.

    Reserved for future payment-provider failure / cancel webhooks.
    """
    locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
    if locked_txn.status != WalletTransaction.Status.PENDING:
        raise PendingTransactionError('Only pending transactions can be failed.')

    locked_txn.status = WalletTransaction.Status.FAILED
    if note:
        locked_txn.note = note
        locked_txn.save(update_fields=['status', 'note', 'updated_at'])
    else:
        locked_txn.save(update_fields=['status', 'updated_at'])
    return locked_txn
