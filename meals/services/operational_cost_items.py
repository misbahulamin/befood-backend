"""Service helpers for operational cost month item replacement."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from meals.models import OperationalCostItem, OperationalCostMonth


@transaction.atomic
def replace_operational_cost_items(
    month: OperationalCostMonth,
    item_payloads: list[dict],
) -> list[OperationalCostItem]:
    """
    Atomically replace all items on an operational cost month.

    Args:
        month: Target operational cost month.
        item_payloads: Dicts with name, amount, optional notes/sort_order.

    Returns:
        Newly created OperationalCostItem rows.
    """
    month.items.all().delete()
    created: list[OperationalCostItem] = []
    for index, item in enumerate(item_payloads):
        name = str(item['name']).strip()
        if not name:
            raise ValidationError({'name': 'Item name is required.'})
        created.append(
            OperationalCostItem.objects.create(
                month=month,
                name=name,
                amount=item['amount'],
                notes=item.get('notes') or '',
                sort_order=item.get('sort_order', index),
            )
        )
    return created
