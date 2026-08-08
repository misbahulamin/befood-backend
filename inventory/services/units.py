"""Inventory unit conversion helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from inventory.models import InventoryUnit

QTY_QUANT = Decimal('0.001')
CONVERTIBLE = {
    (InventoryUnit.G, InventoryUnit.KG): Decimal('0.001'),
    (InventoryUnit.KG, InventoryUnit.G): Decimal('1000'),
    (InventoryUnit.ML, InventoryUnit.L): Decimal('0.001'),
    (InventoryUnit.L, InventoryUnit.ML): Decimal('1000'),
}


class InventoryUnitError(Exception):
    def __init__(self, message: str, *, code: str = 'INVALID_UNIT'):
        super().__init__(message)
        self.code = code


def validate_unit(unit: str) -> str:
    allowed = {c.value for c in InventoryUnit}
    if unit not in allowed:
        raise InventoryUnitError(
            f'Unsupported unit: {unit}.',
            code='UNSUPPORTED_UNIT',
        )
    return unit


def quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


def parse_quantity(quantity) -> Decimal:
    try:
        value = quantity if isinstance(quantity, Decimal) else Decimal(str(quantity))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InventoryUnitError(
            'Quantity must be a valid decimal number.',
            code='INVALID_QUANTITY',
        ) from exc
    if value <= 0:
        raise InventoryUnitError(
            'Quantity must be greater than zero.',
            code='INVALID_QUANTITY',
        )
    return quantize_qty(value)


def convert_to_base(quantity, *, from_unit: str, base_unit: str) -> Decimal:
    """Convert quantity into the item default/base unit."""
    qty = parse_quantity(quantity)
    from_unit = validate_unit(from_unit)
    base_unit = validate_unit(base_unit)

    if from_unit == base_unit:
        return qty

    factor = CONVERTIBLE.get((from_unit, base_unit))
    if factor is None:
        raise InventoryUnitError(
            f'Cannot convert {from_unit} to {base_unit}.',
            code='INCOMPATIBLE_UNIT',
        )
    return quantize_qty(qty * factor)


def convert_signed_to_base(quantity_delta, *, from_unit: str, base_unit: str) -> Decimal:
    """Convert a signed delta (for adjustments) into base unit."""
    try:
        value = (
            quantity_delta
            if isinstance(quantity_delta, Decimal)
            else Decimal(str(quantity_delta))
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InventoryUnitError(
            'Quantity must be a valid decimal number.',
            code='INVALID_QUANTITY',
        ) from exc
    if value == 0:
        raise InventoryUnitError(
            'Quantity delta must not be zero.',
            code='INVALID_QUANTITY',
        )

    sign = Decimal('1') if value > 0 else Decimal('-1')
    base = convert_to_base(abs(value), from_unit=from_unit, base_unit=base_unit)
    return quantize_qty(sign * base)
