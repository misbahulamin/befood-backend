"""Referral commission accrual, reverse, and manual adjustment."""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ledger import (
    InsufficientFundsError as AdminInsufficientFundsError,
)
from admin_wallet.services.ledger import credit_admin_wallet, debit_admin_wallet
from orders.services.subscription_parent import delivery_customer
from referrals.models import ReferralCommission, ReferralRelationship
from referrals.services.eligibility import (
    REASON_REFERRER_MEAL_NOT_CONSUMED,
    ReferralError,
    evaluate_accrual_party_eligibility,
    is_retryable_skip,
)
from wallet.models import WalletTransaction
from wallet.services.ledger import (
    BUCKET_COMMISSION,
    STRATEGY_COMMISSION_ONLY,
    credit_wallet,
    debit_wallet,
    get_or_create_wallet,
)

logger = logging.getLogger(__name__)


def is_referral_enabled() -> bool:
    return bool(getattr(settings, 'REFERRAL_ENABLED', True))


def commission_percent() -> Decimal:
    """Live rate from ReferralProgramSettings (env seeds the singleton on first create)."""
    from referrals.models import ReferralProgramSettings

    return ReferralProgramSettings.load().commission_percent.quantize(Decimal('0.01'))


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _mark_skipped(
    *,
    referrer,
    referred,
    delivery,
    meal_price: Decimal | None,
    percent: Decimal,
    reason: str,
    detail: str = '',
) -> ReferralCommission:
    return ReferralCommission.objects.create(
        referrer=referrer,
        referred=referred,
        order_delivery=delivery,
        meal_service_date=getattr(delivery, 'service_date', None),
        meal_period=getattr(delivery, 'meal_period', '') or '',
        meal_price=meal_price,
        commission_percent=percent,
        commission_amount=Decimal('0.00'),
        status=ReferralCommission.Status.SKIPPED,
        status_reason=reason,
        status_detail=detail[:255],
    )


def _existing_non_pending(delivery) -> ReferralCommission | None:
    return (
        ReferralCommission.objects.select_for_update()
        .filter(order_delivery=delivery, is_manual=False, reversal_of__isnull=True)
        .exclude(status=ReferralCommission.Status.PENDING)
        .order_by('id')
        .first()
    )


def _apply_money_movement(
    *,
    commission: ReferralCommission,
    locked_delivery,
    amount: Decimal,
    actor=None,
) -> ReferralCommission:
    idem_key = f'referral-commission:{locked_delivery.public_id}'
    wallet = get_or_create_wallet(commission.referrer)

    try:
        admin_txn = debit_admin_wallet(
            amount,
            type=AdminWalletTransaction.Type.REFERRAL_COMMISSION,
            method=AdminWalletTransaction.Method.WALLET,
            note=f'Referral commission for delivery {locked_delivery.public_id}',
            reason='referral_commission',
            source='referrals',
            reference=str(commission.public_id),
            idempotency_key=f'admin-{idem_key}',
            order_delivery=locked_delivery,
            customer=commission.referrer,
            metadata={
                'referral_commission_public_id': str(commission.public_id),
                'delivery_public_id': str(locked_delivery.public_id),
            },
        )
        customer_txn = credit_wallet(
            wallet,
            amount,
            type=WalletTransaction.Type.REFERRAL_COMMISSION,
            note=f'Referral commission delivery {locked_delivery.public_id}',
            idempotency_key=idem_key,
            bucket=BUCKET_COMMISSION,
            metadata={
                'referral_commission_public_id': str(commission.public_id),
                'delivery_public_id': str(locked_delivery.public_id),
            },
        )
    except AdminInsufficientFundsError as exc:
        commission.status = ReferralCommission.Status.FAILED
        commission.status_reason = 'ADMIN_FLOAT_INSUFFICIENT'
        commission.status_detail = str(exc)[:255]
        commission.commission_amount = amount
        commission.acted_by = actor
        commission.save(
            update_fields=[
                'status',
                'status_reason',
                'status_detail',
                'commission_amount',
                'acted_by',
                'updated_at',
            ]
        )
        return commission

    commission.status = ReferralCommission.Status.SUCCESS
    commission.status_reason = 'CREDITED'
    commission.status_detail = ''
    commission.commission_amount = amount
    commission.admin_wallet_transaction = admin_txn
    commission.customer_wallet_transaction = customer_txn
    commission.acted_by = actor
    commission.save(
        update_fields=[
            'status',
            'status_reason',
            'status_detail',
            'commission_amount',
            'admin_wallet_transaction',
            'customer_wallet_transaction',
            'acted_by',
            'updated_at',
        ]
    )
    return commission


@transaction.atomic
def credit_referral_commission_for_delivery(delivery, actor=None) -> ReferralCommission | None:
    if not is_referral_enabled():
        return None

    from orders.models import OrderDelivery

    locked = (
        OrderDelivery.objects.select_for_update(of=('self',))
        .select_related(
            'order__customer__user',
            'subscription__customer__user',
        )
        .get(pk=delivery.pk)
    )
    if locked.status != OrderDelivery.DeliveryStatus.DELIVERED:
        return None
    # Referred side must be charged — commission is % of referred payment.
    if locked.payment_status != OrderDelivery.PaymentStatus.CHARGED:
        return None

    existing = _existing_non_pending(locked)
    if existing is not None and not is_retryable_skip(existing):
        return existing

    referred = delivery_customer(locked)
    if referred is None:
        return None

    relationship = (
        ReferralRelationship.objects.select_related('referrer')
        .filter(referred=referred)
        .first()
    )
    if relationship is None:
        return None

    referrer = relationship.referrer
    percent = commission_percent()
    meal_price = locked.charged_amount
    if meal_price is None:
        meal_price = Decimal('0.00')

    party = evaluate_accrual_party_eligibility(
        referrer=referrer,
        referred=referred,
        service_date=locked.service_date,
        meal_period=locked.meal_period or '',
    )
    if not party.ok:
        if existing is not None and is_retryable_skip(existing):
            # Keep retryable skip row; refresh reason/detail if still blocked.
            existing.status_reason = party.reason
            existing.status_detail = party.detail[:255]
            existing.meal_price = meal_price
            existing.commission_percent = percent
            existing.save(
                update_fields=[
                    'status_reason',
                    'status_detail',
                    'meal_price',
                    'commission_percent',
                    'updated_at',
                ]
            )
            return existing
        try:
            return _mark_skipped(
                referrer=referrer,
                referred=referred,
                delivery=locked,
                meal_price=meal_price,
                percent=percent,
                reason=party.reason,
                detail=party.detail,
            )
        except IntegrityError:
            return _existing_non_pending(locked)

    amount = _quantize_money(meal_price * percent / Decimal('100'))
    if amount < Decimal('0.01'):
        if existing is not None and is_retryable_skip(existing):
            existing.status = ReferralCommission.Status.SKIPPED
            existing.status_reason = 'AMOUNT_TOO_SMALL'
            existing.status_detail = 'Commission rounds below 0.01.'
            existing.meal_price = meal_price
            existing.commission_percent = percent
            existing.commission_amount = Decimal('0.00')
            existing.save(
                update_fields=[
                    'status',
                    'status_reason',
                    'status_detail',
                    'meal_price',
                    'commission_percent',
                    'commission_amount',
                    'updated_at',
                ]
            )
            return existing
        try:
            return _mark_skipped(
                referrer=referrer,
                referred=referred,
                delivery=locked,
                meal_price=meal_price,
                percent=percent,
                reason='AMOUNT_TOO_SMALL',
                detail='Commission rounds below 0.01.',
            )
        except IntegrityError:
            return _existing_non_pending(locked)

    # In-place upgrade of retryable skip → pending/success on same row.
    if existing is not None and is_retryable_skip(existing):
        commission = existing
        commission.referrer = referrer
        commission.referred = referred
        commission.meal_service_date = locked.service_date
        commission.meal_period = locked.meal_period or ''
        commission.meal_price = meal_price
        commission.commission_percent = percent
        commission.commission_amount = amount
        commission.status = ReferralCommission.Status.PENDING
        commission.status_reason = 'ACCRUING'
        commission.status_detail = ''
        commission.acted_by = actor
        commission.save(
            update_fields=[
                'referrer',
                'referred',
                'meal_service_date',
                'meal_period',
                'meal_price',
                'commission_percent',
                'commission_amount',
                'status',
                'status_reason',
                'status_detail',
                'acted_by',
                'updated_at',
            ]
        )
    else:
        try:
            commission = ReferralCommission.objects.create(
                referrer=referrer,
                referred=referred,
                order_delivery=locked,
                meal_service_date=locked.service_date,
                meal_period=locked.meal_period or '',
                meal_price=meal_price,
                commission_percent=percent,
                commission_amount=amount,
                status=ReferralCommission.Status.PENDING,
                status_reason='ACCRUING',
                acted_by=actor,
            )
        except IntegrityError:
            raced = _existing_non_pending(locked)
            if raced is not None and not is_retryable_skip(raced):
                return raced
            if raced is not None and is_retryable_skip(raced):
                return credit_referral_commission_for_delivery(locked, actor=actor)
            return raced

    return _apply_money_movement(
        commission=commission,
        locked_delivery=locked,
        amount=amount,
        actor=actor,
    )


@transaction.atomic
def credit_pending_commissions_after_referrer_meal(
    delivery,
    actor=None,
) -> list[ReferralCommission]:
    """
    Secondary trigger: when a customer (as referrer) marks a meal delivered,
    re-evaluate charged referred deliveries for the same service_date + meal_period.
    """
    if not is_referral_enabled():
        return []

    from orders.models import OrderDelivery

    locked = (
        OrderDelivery.objects.select_related(
            'order__customer',
            'subscription__customer',
        ).get(pk=delivery.pk)
    )
    if locked.status != OrderDelivery.DeliveryStatus.DELIVERED:
        return []

    referrer = delivery_customer(locked)
    if referrer is None:
        return []

    referred_ids = list(
        ReferralRelationship.objects.filter(referrer=referrer).values_list(
            'referred_id', flat=True
        )
    )
    if not referred_ids:
        return []

    service_date = locked.service_date
    meal_period = locked.meal_period or ''
    results: list[ReferralCommission] = []

    candidates = (
        OrderDelivery.objects.filter(
            Q(subscription__customer_id__in=referred_ids)
            | Q(order__customer_id__in=referred_ids),
            service_date=service_date,
            meal_period=meal_period,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            payment_status=OrderDelivery.PaymentStatus.CHARGED,
        )
        .order_by('id')
        .distinct()
    )

    for referred_delivery in candidates:
        existing = (
            ReferralCommission.objects.filter(
                order_delivery=referred_delivery,
                is_manual=False,
                reversal_of__isnull=True,
            )
            .exclude(status=ReferralCommission.Status.PENDING)
            .first()
        )
        if existing is not None and not is_retryable_skip(existing):
            continue
        try:
            row = credit_referral_commission_for_delivery(
                referred_delivery, actor=actor
            )
        except Exception:
            logger.exception(
                'Secondary referral accrual failed for delivery_id=%s',
                referred_delivery.pk,
            )
            continue
        if row is not None:
            results.append(row)
    return results


@transaction.atomic
def reverse_referral_commission(
    commission: ReferralCommission,
    *,
    reason: str,
    actor=None,
) -> ReferralCommission:
    reason = (reason or '').strip()
    if not reason:
        raise ReferralError('reason is required.', code='REASON_REQUIRED')

    locked = ReferralCommission.objects.select_for_update().get(pk=commission.pk)
    if locked.status == ReferralCommission.Status.REVERSED:
        raise ReferralError(
            'Commission already reversed.',
            code='ALREADY_REVERSED',
        )
    if locked.status != ReferralCommission.Status.SUCCESS:
        raise ReferralError(
            'Only successful commissions can be reversed.',
            code='INVALID_STATUS',
        )

    amount = locked.commission_amount
    wallet = get_or_create_wallet(locked.referrer)
    idem_key = f'referral-commission-reversal:{locked.public_id}'

    customer_txn = debit_wallet(
        wallet,
        amount,
        type=WalletTransaction.Type.REFERRAL_COMMISSION_REVERSAL,
        note=f'Reversal of referral commission {locked.public_id}',
        idempotency_key=idem_key,
        strategy=STRATEGY_COMMISSION_ONLY,
        metadata={
            'reversed_commission_public_id': str(locked.public_id),
            'reason': reason,
        },
    )
    admin_txn = credit_admin_wallet(
        amount,
        type=AdminWalletTransaction.Type.REFERRAL_COMMISSION_REVERSAL,
        method=AdminWalletTransaction.Method.WALLET,
        note=f'Reversal of referral commission {locked.public_id}',
        reason=reason,
        source='referrals',
        reference=str(locked.public_id),
        idempotency_key=f'admin-{idem_key}',
        customer=locked.referrer,
        customer_wallet_transaction=customer_txn,
        actor_admin=getattr(actor, 'admin_profile', None)
        if actor is not None
        else None,
        metadata={'reason': reason},
    )

    locked.status = ReferralCommission.Status.REVERSED
    locked.status_reason = 'REVERSED'
    locked.status_detail = reason[:255]
    locked.reason = reason[:500]
    locked.acted_by = actor
    locked.save(
        update_fields=[
            'status',
            'status_reason',
            'status_detail',
            'reason',
            'acted_by',
            'updated_at',
        ]
    )

    ReferralCommission.objects.create(
        referrer=locked.referrer,
        referred=locked.referred,
        order_delivery=locked.order_delivery,
        meal_service_date=locked.meal_service_date,
        meal_period=locked.meal_period,
        meal_price=locked.meal_price,
        commission_percent=locked.commission_percent,
        commission_amount=amount,
        status=ReferralCommission.Status.REVERSED,
        status_reason='REVERSAL_RECORD',
        status_detail=reason[:255],
        is_manual=locked.is_manual,
        reversal_of=locked,
        admin_wallet_transaction=admin_txn,
        customer_wallet_transaction=customer_txn,
        acted_by=actor,
        reason=reason[:500],
    )
    return locked


@transaction.atomic
def manual_adjust_referral_commission(
    *,
    referrer,
    amount,
    reason: str,
    actor=None,
    referred=None,
) -> ReferralCommission:
    reason = (reason or '').strip()
    if not reason:
        raise ReferralError('reason is required.', code='REASON_REQUIRED')

    from wallet.services.ledger import validate_amount

    signed = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    if signed == 0:
        raise ReferralError('amount must be non-zero.', code='INVALID_AMOUNT')

    abs_amount = validate_amount(abs(signed))
    wallet = get_or_create_wallet(referrer)
    now_key = timezone.now().strftime('%Y%m%d%H%M%S%f')

    if signed > 0:
        admin_txn = debit_admin_wallet(
            abs_amount,
            type=AdminWalletTransaction.Type.REFERRAL_COMMISSION,
            note='Manual referral commission adjustment',
            reason=reason,
            source='referrals',
            reference=f'manual-adjust-{now_key}',
            idempotency_key=f'admin-manual-referral-{referrer.pk}-{now_key}',
            customer=referrer,
            metadata={'manual': True, 'reason': reason},
        )
        customer_txn = credit_wallet(
            wallet,
            abs_amount,
            type=WalletTransaction.Type.REFERRAL_COMMISSION,
            note='Manual referral commission adjustment',
            idempotency_key=f'manual-referral-{referrer.pk}-{now_key}',
            bucket=BUCKET_COMMISSION,
            metadata={'manual': True, 'reason': reason},
        )
        status = ReferralCommission.Status.SUCCESS
    else:
        customer_txn = debit_wallet(
            wallet,
            abs_amount,
            type=WalletTransaction.Type.REFERRAL_COMMISSION_REVERSAL,
            note='Manual referral commission clawback',
            idempotency_key=f'manual-referral-clawback-{referrer.pk}-{now_key}',
            strategy=STRATEGY_COMMISSION_ONLY,
            metadata={'manual': True, 'reason': reason},
        )
        admin_txn = credit_admin_wallet(
            abs_amount,
            type=AdminWalletTransaction.Type.REFERRAL_COMMISSION_REVERSAL,
            note='Manual referral commission clawback',
            reason=reason,
            source='referrals',
            reference=f'manual-clawback-{now_key}',
            idempotency_key=f'admin-manual-referral-clawback-{referrer.pk}-{now_key}',
            customer=referrer,
            customer_wallet_transaction=customer_txn,
            metadata={'manual': True, 'reason': reason},
        )
        status = ReferralCommission.Status.REVERSED

    return ReferralCommission.objects.create(
        referrer=referrer,
        referred=referred,
        meal_price=None,
        commission_percent=Decimal('0.00'),
        commission_amount=abs_amount,
        status=status,
        status_reason='MANUAL_ADJUSTMENT',
        status_detail=reason[:255],
        is_manual=True,
        admin_wallet_transaction=admin_txn,
        customer_wallet_transaction=customer_txn,
        acted_by=actor,
        reason=reason[:500],
    )
