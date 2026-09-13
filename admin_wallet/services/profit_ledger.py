"""Immutable meal profit ledger recognition and shared snapshot resolution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction

from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import OrderDelivery
from orders.services.subscription_parent import delivery_customer, delivery_meal

_MONEY = Decimal('0.01')
_ZERO = Decimal('0.00')


def _quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_MONEY)


@dataclass(frozen=True)
class ProfitComponents:
    customer: object
    package: object
    meal_period: str
    service_date: object
    meal_price: Decimal
    food_cost: Decimal
    operational_cost: Decimal
    profit_amount: Decimal
    profit_percentage: Decimal
    package_name: str


def resolve_profit_components(delivery: OrderDelivery) -> ProfitComponents | None:
    """
    Resolve frozen financial components for a charged delivery.

    Uses published slot snapshots only (never live catalog recompute).
    Missing slot/snapshots → cost/profit components are ``0.00``.
    Returns ``None`` when customer or meal package cannot be resolved.
    """
    customer = delivery_customer(delivery)
    package = delivery_meal(delivery)
    if customer is None or package is None:
        return None

    meal_price = _quantize(Decimal(delivery.charged_amount or 0))
    food_cost = _ZERO
    operational_cost = _ZERO
    profit_amount = _ZERO

    slot = resolve_published_slot_for_delivery(
        meal_id=package.id,
        service_date=delivery.service_date,
        meal_period=delivery.meal_period,
    )
    if slot is not None:
        if slot.ingredient_cost_snapshot is not None:
            food_cost = _quantize(Decimal(slot.ingredient_cost_snapshot))
        if slot.operational_cost_snapshot is not None:
            operational_cost = _quantize(Decimal(slot.operational_cost_snapshot))
        if slot.profit_snapshot is not None:
            profit_amount = _quantize(Decimal(slot.profit_snapshot))

    if meal_price > 0:
        profit_percentage = _quantize((profit_amount / meal_price) * Decimal('100'))
    else:
        profit_percentage = _ZERO

    package_name = ''
    if delivery.subscription_id:
        package_name = delivery.subscription.meal_name_snapshot or ''
    elif delivery.order_id:
        package_name = delivery.order.meal_name_snapshot or ''
    if not package_name:
        package_name = getattr(package, 'meal_name', '') or ''

    return ProfitComponents(
        customer=customer,
        package=package,
        meal_period=delivery.meal_period,
        service_date=delivery.service_date,
        meal_price=meal_price,
        food_cost=food_cost,
        operational_cost=operational_cost,
        profit_amount=profit_amount,
        profit_percentage=profit_percentage,
        package_name=package_name,
    )


def infer_profit_source(delivery: OrderDelivery) -> str:
    from admin_wallet.models import MealProfitTransaction

    if delivery.marked_by_id is None:
        return MealProfitTransaction.Source.AUTO_DELIVERY
    return MealProfitTransaction.Source.MANUAL_DELIVERY


def recognize_meal_profit(
    delivery: OrderDelivery,
    *,
    source: str | None = None,
) -> object | None:
    """
    Create or return the immutable profit ledger row for a charged delivery.

    No-op (returns ``None``) when the delivery is not charged or components
    cannot be resolved. Idempotent via OneToOne on ``order_delivery``.
    """
    from admin_wallet.models import MealProfitTransaction

    if delivery.payment_status != OrderDelivery.PaymentStatus.CHARGED:
        return None
    if delivery.charged_amount is None:
        return None

    existing = (
        MealProfitTransaction.objects.filter(order_delivery_id=delivery.pk).first()
    )
    if existing is not None:
        return existing

    components = resolve_profit_components(delivery)
    if components is None:
        return None

    resolved_source = source or infer_profit_source(delivery)
    try:
        with transaction.atomic():
            return MealProfitTransaction.objects.create(
                order_delivery=delivery,
                customer=components.customer,
                package=components.package,
                meal_period=components.meal_period,
                service_date=components.service_date,
                meal_price=components.meal_price,
                food_cost=components.food_cost,
                operational_cost=components.operational_cost,
                profit_amount=components.profit_amount,
                profit_percentage=components.profit_percentage,
                source=resolved_source,
                package_name_snapshot=components.package_name,
            )
    except IntegrityError:
        return MealProfitTransaction.objects.filter(order_delivery_id=delivery.pk).get()
