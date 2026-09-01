"""Manual-verification customer funding: request, approve, reject."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from wallet.models import Wallet, WalletTransaction
from wallet.services.ledger import (
    IdempotencyConflictError,
    InsufficientFundsError,
    InvalidAmountError,
    ManualFundingDisabledError,
    PendingTransactionError,
    PlatformFloatError,
    WalletError,
    WalletFrozenError,
    _manual_funding_enabled,
    _sync_admin_wallet_recharge,
    _sync_admin_wallet_withdraw,
    get_or_create_wallet,
    validate_amount,
)

logger = logging.getLogger(__name__)

PROVIDER_RECHARGE_METHODS = frozenset(WalletTransaction.PROVIDER_RECHARGE_METHODS)


class DuplicateProviderRefError(WalletError):
    """Recharge provider transaction id already used."""

    def __init__(self, message: str = 'This payment transaction id was already used.'):
        super().__init__(message)
        self.code = 'DUPLICATE_PROVIDER_REF'


class FundingRequestConflictError(WalletError):
    """Approve/reject attempted on a non-pending funding request."""

    def __init__(self, message: str = 'Funding request has already been processed.'):
        super().__init__(message)
        self.code = 'FUNDING_ALREADY_PROCESSED'


def sanitize_transaction_id(value: str) -> str:
    return (value or '').strip()


def _normalize_payment_method(method: str) -> str:
    normalized = (method or '').strip().lower()
    if normalized not in PROVIDER_RECHARGE_METHODS:
        raise InvalidAmountError(
            'payment_method must be one of: bkash, nagad, bank.'
        )
    return normalized


def _fingerprint_matches(
    existing: WalletTransaction,
    *,
    txn_type: str,
    amount: Decimal,
    method: str,
    external_ref: str,
) -> bool:
    if existing.type != txn_type:
        return False
    if existing.amount != amount:
        return False
    if txn_type == WalletTransaction.Type.RECHARGE:
        return existing.method == method and existing.external_ref == external_ref
    # Withdraw fingerprint: type + amount (method always manual, ref empty).
    return True


def _lookup_idempotent(
    wallet: Wallet,
    idempotency_key: Optional[str],
    *,
    txn_type: str,
    amount: Decimal,
    method: str,
    external_ref: str,
) -> Optional[WalletTransaction]:
    if not idempotency_key:
        return None
    existing = (
        WalletTransaction.objects.filter(wallet=wallet, idempotency_key=idempotency_key)
        .order_by('created_at')
        .first()
    )
    if existing is None:
        return None
    if not _fingerprint_matches(
        existing,
        txn_type=txn_type,
        amount=amount,
        method=method,
        external_ref=external_ref,
    ):
        raise IdempotencyConflictError(
            'Idempotency key was already used with a different funding payload.'
        )
    return existing


def _ensure_active_for_customer(wallet: Wallet) -> None:
    if wallet.status == Wallet.Status.FROZEN:
        raise WalletFrozenError('Wallet is frozen and cannot accept new funding requests.')


def _provider_ref_taken(method: str, external_ref: str, *, exclude_pk=None) -> bool:
    qs = WalletTransaction.objects.filter(
        type=WalletTransaction.Type.RECHARGE,
        method=method,
        external_ref=external_ref,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _schedule_funding_notification(txn_id: int, kind: str) -> None:
    """Schedule admin email after commit; never raise into the request path."""

    def _send():
        try:
            from wallet.services.funding_notifications import (
                notify_admins_pending_recharge,
                notify_admins_pending_withdraw,
            )

            txn = WalletTransaction.objects.select_related(
                'wallet__customer__user',
            ).get(pk=txn_id)
            if kind == 'recharge':
                notify_admins_pending_recharge(txn)
            else:
                notify_admins_pending_withdraw(txn)
        except Exception:
            logger.exception(
                'Failed to send funding admin notification for txn_id=%s kind=%s',
                txn_id,
                kind,
            )

    transaction.on_commit(_send)


@transaction.atomic
def request_recharge(
    customer_profile,
    amount,
    *,
    payment_method: str,
    transaction_id: str,
    note: str = '',
    idempotency_key: Optional[str] = None,
) -> tuple[Wallet, WalletTransaction, bool]:
    """
    Create a pending recharge (no balance change).

    Returns (wallet, txn, created) where created=False on idempotent replay.
    """
    if not _manual_funding_enabled():
        raise ManualFundingDisabledError('Manual wallet funding is currently disabled.')

    amount = validate_amount(amount)
    method = _normalize_payment_method(payment_method)
    external_ref = sanitize_transaction_id(transaction_id)
    if not external_ref:
        raise InvalidAmountError('transaction_id is required.')

    wallet = get_or_create_wallet(customer_profile)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)

    existing = _lookup_idempotent(
        locked,
        idempotency_key,
        txn_type=WalletTransaction.Type.RECHARGE,
        amount=amount,
        method=method,
        external_ref=external_ref,
    )
    if existing is not None:
        locked.refresh_from_db()
        return locked, existing, False

    _ensure_active_for_customer(locked)

    if _provider_ref_taken(method, external_ref):
        raise DuplicateProviderRefError()

    try:
        txn = WalletTransaction.objects.create(
            wallet=locked,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            amount=amount,
            balance_after=None,
            status=WalletTransaction.Status.PENDING,
            method=method,
            external_ref=external_ref,
            idempotency_key=idempotency_key or None,
            note=note or '',
        )
    except IntegrityError as exc:
        # Concurrent idempotency key or duplicate provider ref.
        if idempotency_key:
            raced = (
                WalletTransaction.objects.filter(
                    wallet=locked,
                    idempotency_key=idempotency_key,
                )
                .order_by('created_at')
                .first()
            )
            if raced is not None:
                if not _fingerprint_matches(
                    raced,
                    txn_type=WalletTransaction.Type.RECHARGE,
                    amount=amount,
                    method=method,
                    external_ref=external_ref,
                ):
                    raise IdempotencyConflictError(
                        'Idempotency key was already used with a different funding payload.'
                    ) from exc
                locked.refresh_from_db()
                return locked, raced, False
        if _provider_ref_taken(method, external_ref):
            raise DuplicateProviderRefError() from exc
        raise

    _schedule_funding_notification(txn.pk, 'recharge')
    locked.refresh_from_db()
    return locked, txn, True


@transaction.atomic
def request_withdraw(
    customer_profile,
    amount,
    *,
    note: str = '',
    idempotency_key: Optional[str] = None,
) -> tuple[Wallet, WalletTransaction, bool]:
    """
    Create a pending withdraw and immediately reserve (debit) spendable balance.

    Returns (wallet, txn, created).
    """
    if not _manual_funding_enabled():
        raise ManualFundingDisabledError('Manual wallet funding is currently disabled.')

    amount = validate_amount(amount)
    method = WalletTransaction.Method.MANUAL
    external_ref = ''

    wallet = get_or_create_wallet(customer_profile)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)

    existing = _lookup_idempotent(
        locked,
        idempotency_key,
        txn_type=WalletTransaction.Type.WITHDRAW,
        amount=amount,
        method=method,
        external_ref=external_ref,
    )
    if existing is not None:
        locked.refresh_from_db()
        return locked, existing, False

    _ensure_active_for_customer(locked)

    if amount > locked.balance:
        raise InsufficientFundsError('Insufficient wallet balance.')

    sid = transaction.savepoint()
    new_balance = locked.balance - amount
    locked.balance = new_balance
    locked.save(update_fields=['balance', 'updated_at'])

    try:
        txn = WalletTransaction.objects.create(
            wallet=locked,
            type=WalletTransaction.Type.WITHDRAW,
            direction=WalletTransaction.Direction.DEBIT,
            amount=amount,
            balance_after=new_balance,
            status=WalletTransaction.Status.PENDING,
            method=method,
            external_ref=external_ref,
            idempotency_key=idempotency_key or None,
            note=note or '',
        )
    except IntegrityError as exc:
        transaction.savepoint_rollback(sid)
        locked.refresh_from_db()
        if idempotency_key:
            raced = (
                WalletTransaction.objects.filter(
                    wallet=locked,
                    idempotency_key=idempotency_key,
                )
                .order_by('created_at')
                .first()
            )
            if raced is not None:
                if not _fingerprint_matches(
                    raced,
                    txn_type=WalletTransaction.Type.WITHDRAW,
                    amount=amount,
                    method=method,
                    external_ref=external_ref,
                ):
                    raise IdempotencyConflictError(
                        'Idempotency key was already used with a different funding payload.'
                    ) from exc
                return locked, raced, False
        raise

    transaction.savepoint_commit(sid)
    _schedule_funding_notification(txn.pk, 'withdraw')
    wallet.balance = new_balance
    return locked, txn, True


@transaction.atomic
def approve_recharge(txn: WalletTransaction, *, reviewed_by) -> WalletTransaction:
    """Approve pending recharge: credit customer + Admin Wallet custody."""
    locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
    if locked_txn.type != WalletTransaction.Type.RECHARGE:
        raise PendingTransactionError('Not a recharge funding request.')
    if locked_txn.status != WalletTransaction.Status.PENDING:
        raise FundingRequestConflictError()

    wallet = Wallet.objects.select_for_update().get(pk=locked_txn.wallet_id)
    # Admin resolution allowed even if wallet is frozen after submit.

    new_balance = wallet.balance + locked_txn.amount
    wallet.balance = new_balance
    wallet.save(update_fields=['balance', 'updated_at'])

    now = timezone.now()
    locked_txn.status = WalletTransaction.Status.COMPLETED
    locked_txn.balance_after = new_balance
    locked_txn.reviewed_by = reviewed_by
    locked_txn.reviewed_at = now
    locked_txn.rejection_reason = ''
    locked_txn.save(
        update_fields=[
            'status',
            'balance_after',
            'reviewed_by',
            'reviewed_at',
            'rejection_reason',
            'updated_at',
        ]
    )
    _sync_admin_wallet_recharge(locked_txn)
    return locked_txn


@transaction.atomic
def reject_recharge(
    txn: WalletTransaction,
    *,
    reviewed_by,
    reason: str = '',
) -> WalletTransaction:
    locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
    if locked_txn.type != WalletTransaction.Type.RECHARGE:
        raise PendingTransactionError('Not a recharge funding request.')
    if locked_txn.status != WalletTransaction.Status.PENDING:
        raise FundingRequestConflictError()

    # Lock wallet for consistent ordering with approve paths.
    Wallet.objects.select_for_update().get(pk=locked_txn.wallet_id)

    now = timezone.now()
    locked_txn.status = WalletTransaction.Status.FAILED
    locked_txn.reviewed_by = reviewed_by
    locked_txn.reviewed_at = now
    locked_txn.rejection_reason = (reason or '').strip()[:500]
    locked_txn.save(
        update_fields=[
            'status',
            'reviewed_by',
            'reviewed_at',
            'rejection_reason',
            'updated_at',
        ]
    )
    return locked_txn


@transaction.atomic
def approve_withdraw(txn: WalletTransaction, *, reviewed_by) -> WalletTransaction:
    """
    Finalize pending withdraw and debit Admin Wallet custody.

    Float shortfall raises PlatformFloatError and leaves the request pending
    with review fields untouched (full rollback of this atomic block).
    """
    locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
    if locked_txn.type != WalletTransaction.Type.WITHDRAW:
        raise PendingTransactionError('Not a withdraw funding request.')
    if locked_txn.status != WalletTransaction.Status.PENDING:
        raise FundingRequestConflictError()

    Wallet.objects.select_for_update().get(pk=locked_txn.wallet_id)

    # Custody sync first while still pending conceptually — if it fails, rollback.
    # Mark completed only after custody succeeds so float shortfall is non-mutating.
    now = timezone.now()
    locked_txn.status = WalletTransaction.Status.COMPLETED
    locked_txn.reviewed_by = reviewed_by
    locked_txn.reviewed_at = now
    locked_txn.rejection_reason = ''
    locked_txn.save(
        update_fields=[
            'status',
            'reviewed_by',
            'reviewed_at',
            'rejection_reason',
            'updated_at',
        ]
    )
    try:
        _sync_admin_wallet_withdraw(locked_txn)
    except PlatformFloatError:
        # Full atomic rollback restores pending + untouched review fields.
        raise

    return locked_txn


@transaction.atomic
def reject_withdraw(
    txn: WalletTransaction,
    *,
    reviewed_by,
    reason: str = '',
) -> WalletTransaction:
    locked_txn = WalletTransaction.objects.select_for_update().get(pk=txn.pk)
    if locked_txn.type != WalletTransaction.Type.WITHDRAW:
        raise PendingTransactionError('Not a withdraw funding request.')
    if locked_txn.status != WalletTransaction.Status.PENDING:
        raise FundingRequestConflictError()

    wallet = Wallet.objects.select_for_update().get(pk=locked_txn.wallet_id)
    # Release reservation even if wallet was frozen after submit.
    new_balance = wallet.balance + locked_txn.amount
    wallet.balance = new_balance
    wallet.save(update_fields=['balance', 'updated_at'])

    now = timezone.now()
    locked_txn.status = WalletTransaction.Status.FAILED
    locked_txn.balance_after = new_balance
    locked_txn.reviewed_by = reviewed_by
    locked_txn.reviewed_at = now
    locked_txn.rejection_reason = (reason or '').strip()[:500]
    locked_txn.save(
        update_fields=[
            'status',
            'balance_after',
            'reviewed_by',
            'reviewed_at',
            'rejection_reason',
            'updated_at',
        ]
    )
    return locked_txn
