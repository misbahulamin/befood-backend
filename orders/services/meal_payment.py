"""Charge customer wallet when a meal delivery is marked delivered."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction

from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import OrderDelivery
from wallet.models import WalletTransaction
from wallet.services.ledger import (
    InsufficientFundsError,
    WalletFrozenError,
    debit_wallet,
    get_or_create_wallet,
)

MEAL_DELIVERY_PURPOSE = 'meal_delivery'
IDEMPOTENCY_KEY_PREFIX = 'meal-delivery:'


class MealPaymentError(Exception):
    """Domain error when a meal-delivery wallet charge cannot complete."""

    def __init__(self, message: str, *, code: str = 'MEAL_PAYMENT_FAILED'):
        super().__init__(message)
        self.code = code


def meal_delivery_idempotency_key(delivery: OrderDelivery) -> str:
    return f'{IDEMPOTENCY_KEY_PREFIX}{delivery.public_id}'


def _charge_enabled() -> bool:
    return bool(getattr(settings, 'MEAL_DELIVERY_WALLET_CHARGE_ENABLED', True))


def _use_order_average_fallback() -> bool:
    """Emergency rollback: charge Order.per_meal_price_snapshot instead of slot price."""
    return bool(getattr(settings, 'MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE', False))


def _resolve_charge_amount(delivery: OrderDelivery, meal_id: int, average_price) -> tuple[Decimal, dict]:
    """
    Return (amount, extra_metadata) for the delivery debit.

    Default: published menu slot final_meal_price_snapshot.
    Emergency flag: order/subscription average per-meal snapshot.
    """
    if _use_order_average_fallback():
        amount = Decimal(average_price).quantize(Decimal('0.01'))
        return amount, {
            'charge_source': 'order_average',
            'final_meal_price': str(amount),
        }

    slot = resolve_published_slot_for_delivery(
        meal_id=meal_id,
        service_date=delivery.service_date,
        meal_period=delivery.meal_period,
    )
    if slot is None or slot.final_meal_price_snapshot is None:
        raise MealPaymentError(
            'Published menu slot final price is missing for this delivery; '
            'cannot charge wallet.',
            code='MEAL_SLOT_PRICE_MISSING',
        )
    amount = Decimal(slot.final_meal_price_snapshot).quantize(Decimal('0.01'))
    return amount, {
        'charge_source': 'slot_final_price',
        'final_meal_price': str(amount),
        'ingredient_cost': (
            str(slot.ingredient_cost_snapshot)
            if slot.ingredient_cost_snapshot is not None
            else None
        ),
        'operational_cost': (
            str(slot.operational_cost_snapshot)
            if slot.operational_cost_snapshot is not None
            else None
        ),
        'profit': str(slot.profit_snapshot) if slot.profit_snapshot is not None else None,
    }


def _build_metadata(delivery: OrderDelivery, extra: dict | None = None) -> dict:
    from orders.services.subscription_parent import delivery_meal_name

    metadata = {
        'purpose': MEAL_DELIVERY_PURPOSE,
        'delivery_public_id': str(delivery.public_id),
        'service_date': delivery.service_date.isoformat(),
        'meal_period': delivery.meal_period,
        'meal_name': delivery_meal_name(delivery),
    }
    if delivery.subscription_id:
        metadata['subscription_public_id'] = str(delivery.subscription.public_id)
        metadata['order_public_id'] = None
    elif delivery.order_id:
        metadata['order_public_id'] = str(delivery.order.public_id)
        metadata['subscription_public_id'] = None
    if extra:
        metadata.update(extra)
    return metadata


def _attach_charged_transaction(
    delivery: OrderDelivery,
    txn: WalletTransaction,
    *,
    charged_amount: Decimal,
) -> OrderDelivery:
    delivery.wallet_transaction = txn
    delivery.payment_status = OrderDelivery.PaymentStatus.CHARGED
    delivery.charged_amount = charged_amount
    delivery.save(
        update_fields=[
            'wallet_transaction',
            'payment_status',
            'charged_amount',
            'updated_at',
        ],
    )
    return delivery


@transaction.atomic
def charge_delivered_meal(delivery: OrderDelivery) -> OrderDelivery | None:
    """
    Debit the customer wallet for a delivery that is (or is becoming) delivered.

    Amount is the published lunch/dinner slot final selling price (not package average),
    unless ``MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE`` is enabled for emergency rollback.

    Caller should invoke this only on transition to ``delivered``, inside the same
    atomic block as the status update so wallet failures roll back the mark.

    Returns the updated delivery when a charge ran (or was linked idempotently),
    or ``None`` when charging is disabled by settings.
    """
    if not _charge_enabled():
        return None

    locked = (
        OrderDelivery.objects.select_for_update()
        .select_related(
            'order',
            'order__customer',
            'subscription',
            'subscription__customer',
            'wallet_transaction',
        )
        .get(pk=delivery.pk)
    )

    if locked.status != OrderDelivery.DeliveryStatus.DELIVERED:
        return locked

    if locked.payment_status == OrderDelivery.PaymentStatus.CHARGED and locked.wallet_transaction_id:
        return locked

    from orders.services.subscription_parent import delivery_customer, delivery_meal

    customer = delivery_customer(locked)
    meal = delivery_meal(locked)
    if customer is None or meal is None:
        raise MealPaymentError(
            'Delivery is missing a customer or meal package; cannot charge wallet.',
            code='MEAL_PAYMENT_FAILED',
        )
    average_price = Decimal('0.00')
    if locked.order_id:
        average_price = locked.order.per_meal_price_snapshot
    amount, price_meta = _resolve_charge_amount(locked, meal.id, average_price)
    wallet = get_or_create_wallet(customer)
    idempotency_key = meal_delivery_idempotency_key(locked)

    existing = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            idempotency_key=idempotency_key,
        )
        .order_by('created_at')
        .first()
    )
    if existing is not None:
        if existing.amount != amount:
            raise MealPaymentError(
                'Meal payment idempotency conflict for this delivery.',
                code='MEAL_PAYMENT_IDEMPOTENCY_CONFLICT',
            )
        return _attach_charged_transaction(locked, existing, charged_amount=amount)

    metadata = _build_metadata(locked, extra=price_meta)
    meal_name = (locked.subscription.meal_name_snapshot if locked.subscription_id else locked.order.meal_name_snapshot)
    note = (
        f'Meal payment: {meal_name} '
        f'{locked.meal_period} on {locked.service_date.isoformat()}'
    )

    try:
        txn = debit_wallet(
            wallet,
            amount,
            type=WalletTransaction.Type.PAYMENT,
            method=WalletTransaction.Method.MANUAL,
            status=WalletTransaction.Status.COMPLETED,
            note=note,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
    except InsufficientFundsError as exc:
        raise MealPaymentError(
            'Insufficient wallet balance to charge this meal delivery.',
            code='WALLET_INSUFFICIENT_FOR_MEAL',
        ) from exc
    except WalletFrozenError as exc:
        raise MealPaymentError(
            'Wallet is frozen and cannot be charged for this meal delivery.',
            code='WALLET_FROZEN',
        ) from exc
    except IntegrityError:
        # Concurrent first charge: unique idempotency constraint won the race.
        raced = (
            WalletTransaction.objects.filter(
                wallet=wallet,
                idempotency_key=idempotency_key,
            )
            .order_by('created_at')
            .first()
        )
        if raced is None:
            raise
        return _attach_charged_transaction(locked, raced, charged_amount=amount)

    return _attach_charged_transaction(locked, txn, charged_amount=amount)
