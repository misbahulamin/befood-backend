"""Kitchen usage, wastage, and stock adjustment operations."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from inventory.models import (
    InventoryAdjustment,
    InventoryAuditLog,
    InventoryItem,
    InventoryKitchenUsage,
    InventoryStockMovement,
    InventoryWastage,
)
from inventory.services.ledger import InventoryError, apply_stock_movement
from inventory.services.units import (
    convert_signed_to_base,
    convert_to_base,
    parse_quantity,
    validate_unit,
)


def _get_item(item) -> InventoryItem:
    if isinstance(item, InventoryItem):
        return item
    raise InventoryError('Inventory item is required.', code='ITEM_REQUIRED')


@transaction.atomic
def issue_kitchen_usage(
    *,
    item,
    quantity,
    unit: str | None = None,
    purpose: str = '',
    menu_reference: str = '',
    kitchen_batch: str = '',
    note: str = '',
    issued_by=None,
) -> InventoryKitchenUsage:
    item = _get_item(item)
    unit = validate_unit(unit or item.default_unit)
    qty = parse_quantity(quantity)
    qty_base = convert_to_base(qty, from_unit=unit, base_unit=item.default_unit)
    previous = item.quantity_on_hand

    usage = InventoryKitchenUsage(
        item=item,
        quantity=qty,
        unit=unit,
        quantity_base=qty_base,
        purpose=(purpose or '').strip(),
        menu_reference=(menu_reference or '').strip(),
        kitchen_batch=(kitchen_batch or '').strip(),
        note=note or '',
        issued_by=issued_by,
        quantity_after=Decimal('0'),
    )
    # Save after movement so quantity_after is known; create stub then update.
    usage.save()

    movement = apply_stock_movement(
        item,
        movement_type=InventoryStockMovement.Type.KITCHEN_USAGE,
        quantity_delta=-qty_base,
        actor_admin=issued_by,
        note=purpose or note,
        kitchen_usage=usage,
    )
    usage.quantity_after = movement.quantity_after
    usage.save(update_fields=['quantity_after'])

    InventoryAuditLog.objects.create(
        actor_admin=issued_by,
        action=InventoryAuditLog.Action.STOCK_USED,
        item=item,
        previous_value={'quantity_on_hand': str(previous)},
        new_value={
            'quantity_on_hand': str(movement.quantity_after),
            'quantity_used': str(qty_base),
            'purpose': usage.purpose,
        },
        reference_id=str(usage.public_id),
    )
    return usage


@transaction.atomic
def record_wastage(
    *,
    item,
    quantity,
    reason: str,
    unit: str | None = None,
    note: str = '',
    recorded_by=None,
) -> InventoryWastage:
    item = _get_item(item)
    reason_clean = (reason or '').strip()
    if not reason_clean:
        raise InventoryError('Wastage reason is required.', code='REASON_REQUIRED')
    unit = validate_unit(unit or item.default_unit)
    qty = parse_quantity(quantity)
    qty_base = convert_to_base(qty, from_unit=unit, base_unit=item.default_unit)
    previous = item.quantity_on_hand

    wastage = InventoryWastage.objects.create(
        item=item,
        quantity=qty,
        unit=unit,
        quantity_base=qty_base,
        reason=reason_clean,
        note=note or '',
        recorded_by=recorded_by,
        quantity_after=Decimal('0'),
    )
    movement = apply_stock_movement(
        item,
        movement_type=InventoryStockMovement.Type.WASTAGE,
        quantity_delta=-qty_base,
        actor_admin=recorded_by,
        note=reason_clean,
        wastage=wastage,
    )
    wastage.quantity_after = movement.quantity_after
    wastage.save(update_fields=['quantity_after'])

    InventoryAuditLog.objects.create(
        actor_admin=recorded_by,
        action=InventoryAuditLog.Action.WASTAGE_ADDED,
        item=item,
        previous_value={'quantity_on_hand': str(previous)},
        new_value={
            'quantity_on_hand': str(movement.quantity_after),
            'quantity': str(qty_base),
            'reason': reason_clean,
        },
        reference_id=str(wastage.public_id),
    )
    return wastage


@transaction.atomic
def adjust_stock(
    *,
    item,
    quantity_delta,
    reason: str,
    unit: str | None = None,
    note: str = '',
    adjusted_by=None,
) -> InventoryAdjustment:
    item = _get_item(item)
    reason_clean = (reason or '').strip()
    if not reason_clean:
        raise InventoryError('Adjustment reason is required.', code='REASON_REQUIRED')
    unit = validate_unit(unit or item.default_unit)
    delta_base = convert_signed_to_base(
        quantity_delta,
        from_unit=unit,
        base_unit=item.default_unit,
    )
    previous = item.quantity_on_hand

    try:
        raw_delta = (
            quantity_delta
            if isinstance(quantity_delta, Decimal)
            else Decimal(str(quantity_delta))
        )
    except Exception as exc:  # noqa: BLE001
        raise InventoryError(
            'Quantity must be a valid decimal number.',
            code='INVALID_QUANTITY',
        ) from exc

    adjustment = InventoryAdjustment.objects.create(
        item=item,
        quantity_delta=raw_delta,
        unit=unit,
        quantity_delta_base=delta_base,
        reason=reason_clean,
        note=note or '',
        adjusted_by=adjusted_by,
        quantity_after=Decimal('0'),
    )
    movement = apply_stock_movement(
        item,
        movement_type=InventoryStockMovement.Type.ADJUSTMENT,
        quantity_delta=delta_base,
        actor_admin=adjusted_by,
        note=reason_clean,
        adjustment=adjustment,
    )
    adjustment.quantity_after = movement.quantity_after
    adjustment.save(update_fields=['quantity_after'])

    InventoryAuditLog.objects.create(
        actor_admin=adjusted_by,
        action=InventoryAuditLog.Action.STOCK_ADJUSTED,
        item=item,
        previous_value={'quantity_on_hand': str(previous)},
        new_value={
            'quantity_on_hand': str(movement.quantity_after),
            'quantity_delta': str(delta_base),
            'reason': reason_clean,
        },
        reference_id=str(adjustment.public_id),
    )
    return adjustment
