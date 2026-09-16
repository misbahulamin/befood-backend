"""Manual admin delivery-fee deduction from customer wallet."""

from __future__ import annotations

import calendar
from decimal import Decimal
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.services.wallet_balance_thresholds import evaluate_meal_stop_after_debit
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import DeliveryFeePayment, Wallet, WalletTransaction
from wallet.services.ledger import (
    IdempotencyConflictError,
    InsufficientFundsError,
    InvalidAmountError,
    WalletError,
    WalletFrozenError,
    debit_wallet,
    get_or_create_wallet,
    validate_amount,
)


class DeliveryFeeError(WalletError):
    """Base delivery-fee domain error."""


class DeliveryFeeAlreadyPaidError(DeliveryFeeError):
    def __init__(self, message: str = 'Delivery fee already paid for this month.'):
        super().__init__(message)
        self.code = 'DELIVERY_FEE_ALREADY_PAID'


class DeliveryFeePeriodError(DeliveryFeeError):
    def __init__(self, message: str = 'Invalid payment month or year.'):
        super().__init__(message)
        self.code = 'DELIVERY_FEE_INVALID_PERIOD'


def billing_period_label(year: int, month: int) -> str:
    return f'{calendar.month_name[month]} {year}'


def _validate_period(payment_month: int, payment_year: int) -> tuple[int, int]:
    try:
        month = int(payment_month)
        year = int(payment_year)
    except (TypeError, ValueError) as exc:
        raise DeliveryFeePeriodError('payment_month and payment_year must be integers.') from exc
    if month < 1 or month > 12:
        raise DeliveryFeePeriodError('payment_month must be between 1 and 12.')
    if year < 2000 or year > 2100:
        raise DeliveryFeePeriodError('payment_year is out of allowed range.')
    return month, year


def _admin_display(admin: AdminProfile | None) -> str:
    if admin is None:
        return ''
    user = admin.user
    full = f'{user.first_name} {user.last_name}'.strip()
    return full or user.email or user.username


def _find_idempotent_payment(
    wallet: Wallet,
    idempotency_key: Optional[str],
) -> DeliveryFeePayment | None:
    if not idempotency_key:
        return None
    txn = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            idempotency_key=idempotency_key,
            type=WalletTransaction.Type.DELIVERY_FEE_PAYMENT,
        )
        .select_related('delivery_fee_payment')
        .order_by('created_at')
        .first()
    )
    if txn is None:
        return None
    payment = getattr(txn, 'delivery_fee_payment', None)
    return payment


def serialize_delivery_fee_payment(payment: DeliveryFeePayment) -> dict:
    admin = payment.deducted_by_admin
    return {
        'public_id': str(payment.public_id),
        'customer_public_id': str(payment.customer.public_id),
        'amount': f'{payment.amount.quantize(Decimal("0.01")):.2f}',
        'payment_month': payment.payment_month,
        'payment_year': payment.payment_year,
        'period_label': billing_period_label(payment.payment_year, payment.payment_month),
        'status': payment.status,
        'reason': payment.reason,
        'source': payment.source,
        'deducted_by_admin': _admin_display(admin) or None,
        'deducted_by_admin_id': admin.pk if admin else None,
        'wallet_transaction_public_id': str(payment.wallet_transaction.public_id),
        'wallet_balance_after': (
            f'{payment.wallet_transaction.balance_after.quantize(Decimal("0.01")):.2f}'
            if payment.wallet_transaction.balance_after is not None
            else None
        ),
        'created_at': payment.created_at,
        'paid_at': payment.created_at,
    }


@transaction.atomic
def charge_delivery_fee(
    customer: CustomerProfile,
    amount,
    *,
    payment_month: int,
    payment_year: int,
    reason: str,
    actor_admin: AdminProfile,
    idempotency_key: Optional[str] = None,
    source: str = DeliveryFeePayment.Source.MANUAL,
    fee_rule_code: str = '',
    service_area_public_id=None,
    metadata: Optional[dict] = None,
) -> tuple[DeliveryFeePayment, bool]:
    """
    Debit customer wallet for a monthly delivery fee.

    Returns (payment, created). created=False on idempotent replay.
    Does not mutate Admin Wallet cash (custody model).
    """
    if actor_admin is None:
        raise DeliveryFeeError('Verified admin actor is required.')

    reason_clean = (reason or '').strip()
    if not reason_clean:
        raise DeliveryFeeError('reason is required.')

    month, year = _validate_period(payment_month, payment_year)
    amount = validate_amount(amount)
    wallet = get_or_create_wallet(customer)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)

    existing = _find_idempotent_payment(locked, idempotency_key)
    if existing is not None:
        existing_amount = existing.amount.quantize(Decimal('0.01'))
        if existing_amount != amount:
            raise IdempotencyConflictError(
                'Idempotency key was reused with a different amount.'
            )
        if (
            existing.payment_month != month
            or existing.payment_year != year
            or existing.customer_id != customer.pk
        ):
            raise IdempotencyConflictError(
                'Idempotency key was reused with different billing period or customer.'
            )
        return existing, False

    paid_exists = (
        DeliveryFeePayment.objects.select_for_update()
        .filter(
            customer=customer,
            payment_year=year,
            payment_month=month,
            status=DeliveryFeePayment.Status.PAID,
        )
        .exists()
    )
    if paid_exists:
        raise DeliveryFeeAlreadyPaidError(
            f'Delivery fee already paid for {billing_period_label(year, month)}.'
        )

    period = billing_period_label(year, month)
    note = f'{period} Delivery Fee'
    meta = {
        'purpose': 'delivery_fee',
        'payment_month': month,
        'payment_year': year,
        'reason': reason_clean,
        'actor_admin_id': actor_admin.pk,
        'actor_admin_name': _admin_display(actor_admin),
        **(metadata or {}),
    }

    try:
        txn = debit_wallet(
            locked,
            amount,
            type=WalletTransaction.Type.DELIVERY_FEE_PAYMENT,
            method=WalletTransaction.Method.MANUAL,
            status=WalletTransaction.Status.COMPLETED,
            note=note,
            idempotency_key=idempotency_key or None,
            metadata=meta,
        )
    except InsufficientFundsError as exc:
        raise InsufficientFundsError('Insufficient wallet balance') from exc

    now = timezone.now()
    txn.reviewed_by = actor_admin.user
    txn.reviewed_at = now
    txn.save(update_fields=['reviewed_by', 'reviewed_at', 'updated_at'])

    try:
        payment = DeliveryFeePayment.objects.create(
            customer=customer,
            amount=amount,
            payment_month=month,
            payment_year=year,
            status=DeliveryFeePayment.Status.PAID,
            deducted_by_admin=actor_admin,
            wallet_transaction=txn,
            reason=reason_clean,
            source=source or DeliveryFeePayment.Source.MANUAL,
            fee_rule_code=(fee_rule_code or '').strip(),
            service_area_public_id=service_area_public_id,
            metadata=metadata or {},
        )
    except IntegrityError as exc:
        raise DeliveryFeeAlreadyPaidError(
            f'Delivery fee already paid for {period}.'
        ) from exc

    txn_meta = dict(txn.metadata or {})
    txn_meta['delivery_fee_payment_public_id'] = str(payment.public_id)
    txn.metadata = txn_meta
    txn.save(update_fields=['metadata', 'updated_at'])

    evaluate_meal_stop_after_debit(customer)

    payment_id = payment.pk

    def _notify():
        from wallet.services.delivery_fee_notifications import (
            notify_customer_delivery_fee_deducted,
        )

        notify_customer_delivery_fee_deducted(payment_id)

    transaction.on_commit(_notify)

    return payment, True


def list_customer_delivery_fee_payments(customer: CustomerProfile):
    return (
        DeliveryFeePayment.objects.filter(customer=customer)
        .select_related(
            'deducted_by_admin__user',
            'wallet_transaction',
            'customer__user',
        )
        .order_by('-payment_year', '-payment_month', '-created_at', '-id')
    )


def build_delivery_fee_context(customer: CustomerProfile) -> dict:
    from user_management.services.admin_customer import (
        _display_name,
        build_active_subscription_payload,
        get_customer_wallet,
    )
    from user_management.validators import format_bd_phone_e164

    wallet = get_customer_wallet(customer)
    if wallet is None:
        wallet = get_or_create_wallet(customer)

    history = [
        serialize_delivery_fee_payment(p)
        for p in list_customer_delivery_fee_payments(customer)[:24]
    ]
    current_month_paid = next(
        (
            h
            for h in history
            if h['status'] == DeliveryFeePayment.Status.PAID
            and h['payment_year'] == timezone.localdate().year
            and h['payment_month'] == timezone.localdate().month
        ),
        None,
    )

    phone = customer.phone or ''
    try:
        phone_display = format_bd_phone_e164(phone) if phone else ''
    except Exception:
        phone_display = phone

    return {
        'customer_public_id': str(customer.public_id),
        'customer_name': _display_name(customer),
        'phone': phone,
        'phone_display': phone_display or phone,
        'wallet_balance': f'{wallet.balance.quantize(Decimal("0.01")):.2f}',
        'recharge_balance': f'{wallet.recharge_balance.quantize(Decimal("0.01")):.2f}',
        'commission_balance': f'{wallet.commission_balance.quantize(Decimal("0.01")):.2f}',
        'wallet_status': wallet.status,
        'wallet_currency': wallet.currency,
        'active_subscription': build_active_subscription_payload(customer),
        'current_month_delivery_fee_paid': (
            current_month_paid['amount'] if current_month_paid else '0.00'
        ),
        'delivery_fee_history': history,
    }
