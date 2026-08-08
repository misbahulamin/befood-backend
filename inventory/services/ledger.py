"""Inventory stock ledger primitives."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.db import transaction

from inventory.models import InventoryItem, InventoryStockMovement

MONEY_QUANT = Decimal('0.0001')
VALUE_QUANT = Decimal('0.01')


class InventoryError(Exception):
    def __init__(self, message: str, *, code: str = 'INVENTORY_ERROR'):
        super().__init__(message)
        self.code = code


class InsufficientStockError(InventoryError):
    def __init__(self, available: Decimal, unit: str):
        message = f'পর্যাপ্ত stock নেই। Available Stock: {available} {unit}'
        super().__init__(message, code='INSUFFICIENT_STOCK')
        self.available = available
        self.unit = unit


def inventory_value(item: InventoryItem) -> Decimal:
    if item.quantity_on_hand <= 0 or item.average_unit_cost is None:
        return Decimal('0.00')
    return (item.quantity_on_hand * item.average_unit_cost).quantize(VALUE_QUANT)


def compute_wac(
    *,
    quantity_on_hand: Decimal,
    average_unit_cost: Optional[Decimal],
    receive_qty: Decimal,
    unit_cost: Decimal,
) -> Optional[Decimal]:
    """Weighted average cost after receiving stock."""
    q = Decimal(receive_qty)
    c = Decimal(unit_cost)
    Q = Decimal(quantity_on_hand)
    A = Decimal(average_unit_cost or 0)
    total_qty = Q + q
    if total_qty <= 0:
        return average_unit_cost
    if Q <= 0 or average_unit_cost is None:
        return c.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    return (((Q * A) + (q * c)) / total_qty).quantize(
        MONEY_QUANT, rounding=ROUND_HALF_UP
    )


def reverse_wac(
    *,
    quantity_on_hand: Decimal,
    average_unit_cost: Optional[Decimal],
    remove_qty: Decimal,
    unit_cost: Decimal,
) -> Optional[Decimal]:
    """Approximate WAC after reversing a purchase receipt."""
    Q = Decimal(quantity_on_hand)
    q = Decimal(remove_qty)
    remaining = Q - q
    if remaining <= 0:
        return None
    if average_unit_cost is None:
        return None
    A = Decimal(average_unit_cost)
    c = Decimal(unit_cost)
    numerator = (Q * A) - (q * c)
    if numerator < 0:
        return None
    return (numerator / remaining).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


@transaction.atomic
def apply_stock_movement(
    item: InventoryItem,
    *,
    movement_type: str,
    quantity_delta: Decimal,
    actor_admin=None,
    note: str = '',
    purchase=None,
    purchase_line=None,
    kitchen_usage=None,
    wastage=None,
    adjustment=None,
    unit_cost_at_movement: Optional[Decimal] = None,
    update_wac: bool = False,
    reverse_wac_cost: Optional[Decimal] = None,
    metadata: Optional[dict] = None,
) -> InventoryStockMovement:
    """
    Lock item, append movement, update on-hand (and optional WAC).

    quantity_delta is in the item default unit (signed).
    """
    locked = InventoryItem.objects.select_for_update().get(pk=item.pk)
    before = locked.quantity_on_hand
    delta = Decimal(quantity_delta)
    after = before + delta

    if after < 0:
        raise InsufficientStockError(available=before, unit=locked.default_unit)

    if update_wac and delta > 0 and unit_cost_at_movement is not None:
        locked.average_unit_cost = compute_wac(
            quantity_on_hand=before,
            average_unit_cost=locked.average_unit_cost,
            receive_qty=delta,
            unit_cost=unit_cost_at_movement,
        )
    elif reverse_wac_cost is not None and delta < 0:
        locked.average_unit_cost = reverse_wac(
            quantity_on_hand=before,
            average_unit_cost=locked.average_unit_cost,
            remove_qty=abs(delta),
            unit_cost=reverse_wac_cost,
        )
    elif after == 0 and delta < 0 and movement_type == InventoryStockMovement.Type.PURCHASE_REVERSAL:
        locked.average_unit_cost = None

    locked.quantity_on_hand = after
    locked.save(
        update_fields=['quantity_on_hand', 'average_unit_cost', 'updated_at']
    )

    movement = InventoryStockMovement.objects.create(
        item=locked,
        type=movement_type,
        quantity_delta=delta,
        quantity_before=before,
        quantity_after=after,
        unit=locked.default_unit,
        actor_admin=actor_admin,
        note=note or '',
        purchase=purchase,
        purchase_line=purchase_line,
        kitchen_usage=kitchen_usage,
        wastage=wastage,
        adjustment=adjustment,
        unit_cost_at_movement=unit_cost_at_movement,
        metadata=metadata or {},
    )

    item.quantity_on_hand = after
    item.average_unit_cost = locked.average_unit_cost
    return movement


def ledger_sum(item: InventoryItem) -> Decimal:
    from django.db.models import Sum

    total = item.movements.aggregate(total=Sum('quantity_delta'))['total']
    return Decimal(total or 0).quantize(Decimal('0.001'))
