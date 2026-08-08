"""Inventory item master services."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import transaction

from inventory.models import InventoryAuditLog, InventoryItem, InventoryUnit
from inventory.services.ledger import InventoryError
from inventory.services.units import validate_unit


def normalize_item_name(name: str) -> str:
    return ' '.join((name or '').strip().split()).casefold()


def stock_signals(item: InventoryItem) -> dict:
    return {
        'out_of_stock': item.is_out_of_stock,
        'low_stock': item.is_low_stock,
    }


@transaction.atomic
def create_item(
    *,
    name: str,
    default_unit: str,
    category: str = '',
    status: str = InventoryItem.Status.ACTIVE,
    minimum_stock_level=None,
    linked_ingredient=None,
    created_by=None,
) -> InventoryItem:
    cleaned = ' '.join((name or '').strip().split())
    if not cleaned:
        raise InventoryError('Item name is required.', code='NAME_REQUIRED')
    normalized = normalize_item_name(cleaned)
    if InventoryItem.objects.filter(name_normalized=normalized).exists():
        raise InventoryError(
            'An inventory item with this name already exists.',
            code='DUPLICATE_ITEM_NAME',
        )
    unit = validate_unit(default_unit)
    if status not in InventoryItem.Status.values:
        raise InventoryError('Invalid item status.', code='INVALID_STATUS')

    min_level = None
    if minimum_stock_level is not None and minimum_stock_level != '':
        min_level = Decimal(str(minimum_stock_level))
        if min_level < 0:
            raise InventoryError(
                'Minimum stock level cannot be negative.',
                code='INVALID_MINIMUM_STOCK',
            )

    item = InventoryItem.objects.create(
        name=cleaned,
        name_normalized=normalized,
        default_unit=unit,
        category=(category or '').strip(),
        status=status,
        minimum_stock_level=min_level,
        linked_ingredient=linked_ingredient,
        created_by=created_by,
    )
    InventoryAuditLog.objects.create(
        actor_admin=created_by,
        action=InventoryAuditLog.Action.ITEM_CREATED,
        item=item,
        new_value={
            'name': item.name,
            'default_unit': item.default_unit,
            'category': item.category,
            'status': item.status,
            'minimum_stock_level': (
                str(item.minimum_stock_level)
                if item.minimum_stock_level is not None
                else None
            ),
        },
        reference_id=str(item.public_id),
    )
    return item


@transaction.atomic
def update_item(
    item: InventoryItem,
    *,
    actor_admin=None,
    name: Optional[str] = None,
    default_unit: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    minimum_stock_level=...,
    linked_ingredient=...,
) -> InventoryItem:
    previous = {
        'name': item.name,
        'default_unit': item.default_unit,
        'category': item.category,
        'status': item.status,
        'minimum_stock_level': (
            str(item.minimum_stock_level)
            if item.minimum_stock_level is not None
            else None
        ),
    }
    update_fields = ['updated_at']

    if name is not None:
        cleaned = ' '.join(name.strip().split())
        if not cleaned:
            raise InventoryError('Item name is required.', code='NAME_REQUIRED')
        normalized = normalize_item_name(cleaned)
        conflict = (
            InventoryItem.objects.filter(name_normalized=normalized)
            .exclude(pk=item.pk)
            .exists()
        )
        if conflict:
            raise InventoryError(
                'An inventory item with this name already exists.',
                code='DUPLICATE_ITEM_NAME',
            )
        item.name = cleaned
        item.name_normalized = normalized
        update_fields.extend(['name', 'name_normalized'])

    if default_unit is not None:
        if item.quantity_on_hand != 0 or item.movements.exists():
            raise InventoryError(
                'Cannot change default unit after stock movements exist.',
                code='UNIT_LOCKED',
            )
        item.default_unit = validate_unit(default_unit)
        update_fields.append('default_unit')

    if category is not None:
        item.category = category.strip()
        update_fields.append('category')

    if status is not None:
        if status not in InventoryItem.Status.values:
            raise InventoryError('Invalid item status.', code='INVALID_STATUS')
        item.status = status
        update_fields.append('status')

    if minimum_stock_level is not ...:
        if minimum_stock_level is None or minimum_stock_level == '':
            item.minimum_stock_level = None
        else:
            level = Decimal(str(minimum_stock_level))
            if level < 0:
                raise InventoryError(
                    'Minimum stock level cannot be negative.',
                    code='INVALID_MINIMUM_STOCK',
                )
            item.minimum_stock_level = level
        update_fields.append('minimum_stock_level')

    if linked_ingredient is not ...:
        item.linked_ingredient = linked_ingredient
        update_fields.append('linked_ingredient')

    item.save(update_fields=list(dict.fromkeys(update_fields)))
    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.ITEM_UPDATED,
        item=item,
        previous_value=previous,
        new_value={
            'name': item.name,
            'default_unit': item.default_unit,
            'category': item.category,
            'status': item.status,
            'minimum_stock_level': (
                str(item.minimum_stock_level)
                if item.minimum_stock_level is not None
                else None
            ),
        },
        reference_id=str(item.public_id),
    )
    return item


# Silence unused import lint for InventoryUnit re-export convenience
_ = InventoryUnit
