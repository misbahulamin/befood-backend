"""Inventory purchase create/confirm/cancel and invoice attach."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.db import transaction
from django.utils import timezone

from admin_wallet.services.ledger import (
    AdminWalletError,
    InsufficientFundsError,
)
from admin_wallet.services.operations import (
    credit_for_inventory_purchase_reversal,
    debit_for_inventory_purchase,
)
from inventory.models import (
    InventoryAuditLog,
    InventoryItem,
    InventoryPurchase,
    InventoryPurchaseLine,
    InventoryStockMovement,
)
from inventory.services.ledger import InventoryError, apply_stock_movement
from inventory.services.units import convert_to_base, parse_quantity, validate_unit

MONEY = Decimal('0.01')
UNIT_COST = Decimal('0.0001')


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _unit_cost(line_total: Decimal, qty_base: Decimal) -> Decimal:
    if qty_base <= 0:
        raise InventoryError('Invalid base quantity.', code='INVALID_QUANTITY')
    return (line_total / qty_base).quantize(UNIT_COST, rounding=ROUND_HALF_UP)


@transaction.atomic
def create_purchase(
    *,
    lines: list[dict],
    actor_admin=None,
    supplier: str = '',
    note: str = '',
    purchase_date=None,
    confirm: bool = False,
    invoice=None,
) -> InventoryPurchase:
    if not lines:
        raise InventoryError('At least one purchase line is required.', code='LINES_REQUIRED')

    purchase = InventoryPurchase.objects.create(
        status=InventoryPurchase.Status.DRAFT,
        purchase_date=purchase_date or timezone.localdate(),
        supplier=(supplier or '').strip(),
        note=note or '',
        created_by=actor_admin,
        invoice=invoice,
    )

    total = Decimal('0.00')
    for raw in lines:
        item = raw['item']
        if not isinstance(item, InventoryItem):
            raise InventoryError('Invalid inventory item.', code='ITEM_REQUIRED')
        unit = validate_unit(raw.get('unit') or item.default_unit)
        qty = parse_quantity(raw['quantity'])
        qty_base = convert_to_base(qty, from_unit=unit, base_unit=item.default_unit)
        line_total = _money(raw['line_total'])
        if line_total <= 0:
            raise InventoryError(
                'Line total must be greater than zero.',
                code='INVALID_AMOUNT',
            )
        unit_cost = _unit_cost(line_total, qty_base)
        InventoryPurchaseLine.objects.create(
            purchase=purchase,
            item=item,
            quantity=qty,
            unit=unit,
            quantity_base=qty_base,
            line_total=line_total,
            unit_cost=unit_cost,
        )
        total += line_total

    purchase.total_amount = total.quantize(MONEY)
    purchase.save(update_fields=['total_amount', 'updated_at'])

    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.PURCHASE_ADDED,
        purchase=purchase,
        new_value={
            'total_amount': str(purchase.total_amount),
            'supplier': purchase.supplier,
            'line_count': len(lines),
        },
        reference_id=str(purchase.public_id),
    )
    if invoice:
        InventoryAuditLog.objects.create(
            actor_admin=actor_admin,
            action=InventoryAuditLog.Action.INVOICE_UPLOADED,
            purchase=purchase,
            reference_id=str(purchase.public_id),
        )

    if confirm:
        purchase = confirm_purchase(purchase, actor_admin=actor_admin)
    return purchase


@transaction.atomic
def attach_invoice(purchase: InventoryPurchase, *, invoice, actor_admin=None) -> InventoryPurchase:
    if purchase.status == InventoryPurchase.Status.CANCELLED:
        raise InventoryError(
            'Cannot attach invoice to a cancelled purchase.',
            code='PURCHASE_CANCELLED',
        )
    purchase.invoice = invoice
    purchase.save(update_fields=['invoice', 'updated_at'])
    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.INVOICE_UPLOADED,
        purchase=purchase,
        reference_id=str(purchase.public_id),
    )
    return purchase


@transaction.atomic
def confirm_purchase(
    purchase: InventoryPurchase,
    *,
    actor_admin=None,
) -> InventoryPurchase:
    locked = InventoryPurchase.objects.select_for_update().get(pk=purchase.pk)
    if locked.status == InventoryPurchase.Status.CONFIRMED:
        return locked
    if locked.status == InventoryPurchase.Status.CANCELLED:
        raise InventoryError(
            'Cancelled purchase cannot be confirmed.',
            code='PURCHASE_CANCELLED',
        )
    lines = list(locked.lines.select_related('item').all())
    if not lines:
        raise InventoryError('Purchase has no lines.', code='LINES_REQUIRED')

    try:
        wallet_txn = debit_for_inventory_purchase(
            locked.total_amount,
            purchase_public_id=locked.public_id,
            actor_admin=actor_admin,
            note=locked.note,
            reason=f'Inventory purchase {locked.public_id}',
        )
    except InsufficientFundsError as exc:
        raise InventoryError(
            'Admin Wallet-এ পর্যাপ্ত balance নেই।',
            code='INSUFFICIENT_WALLET_BALANCE',
        ) from exc
    except AdminWalletError as exc:
        raise InventoryError(str(exc), code=getattr(exc, 'code', 'ADMIN_WALLET_ERROR')) from exc

    for line in lines:
        apply_stock_movement(
            line.item,
            movement_type=InventoryStockMovement.Type.PURCHASE,
            quantity_delta=line.quantity_base,
            actor_admin=actor_admin,
            note=f'Purchase {locked.public_id}',
            purchase=locked,
            purchase_line=line,
            unit_cost_at_movement=line.unit_cost,
            update_wac=True,
        )

    locked.status = InventoryPurchase.Status.CONFIRMED
    locked.confirmed_by = actor_admin
    locked.confirmed_at = timezone.now()
    locked.wallet_transaction = wallet_txn
    locked.save(
        update_fields=[
            'status',
            'confirmed_by',
            'confirmed_at',
            'wallet_transaction',
            'updated_at',
        ]
    )

    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.PURCHASE_CONFIRMED,
        purchase=locked,
        new_value={
            'status': locked.status,
            'total_amount': str(locked.total_amount),
            'wallet_transaction_public_id': str(wallet_txn.public_id),
            'invoice_present': bool(locked.invoice),
        },
        reference_id=str(locked.public_id),
        metadata={'missing_invoice': not bool(locked.invoice)},
    )
    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.WALLET_DEDUCTED,
        purchase=locked,
        new_value={
            'amount': str(locked.total_amount),
            'wallet_transaction_public_id': str(wallet_txn.public_id),
        },
        reference_id=str(wallet_txn.public_id),
    )
    return locked


@transaction.atomic
def cancel_purchase(
    purchase: InventoryPurchase,
    *,
    actor_admin=None,
    reason: str = '',
) -> InventoryPurchase:
    locked = InventoryPurchase.objects.select_for_update().get(pk=purchase.pk)

    if locked.status == InventoryPurchase.Status.DRAFT:
        locked.status = InventoryPurchase.Status.CANCELLED
        locked.cancelled_by = actor_admin
        locked.cancelled_at = timezone.now()
        locked.save(
            update_fields=['status', 'cancelled_by', 'cancelled_at', 'updated_at']
        )
        InventoryAuditLog.objects.create(
            actor_admin=actor_admin,
            action=InventoryAuditLog.Action.PURCHASE_CANCELLED,
            purchase=locked,
            previous_value={'status': InventoryPurchase.Status.DRAFT},
            new_value={'status': locked.status},
            reference_id=str(locked.public_id),
            metadata={'reason': reason or 'Draft discarded'},
        )
        return locked

    if locked.status == InventoryPurchase.Status.CANCELLED:
        return locked

    if locked.status != InventoryPurchase.Status.CONFIRMED:
        raise InventoryError(
            'Only draft or confirmed purchases can be cancelled.',
            code='INVALID_PURCHASE_STATUS',
        )

    lines = list(locked.lines.select_related('item').all())
    # Cancel rule: each item must still have enough on-hand to reverse full purchased qty.
    for line in lines:
        item = InventoryItem.objects.select_for_update().get(pk=line.item_id)
        if item.quantity_on_hand < line.quantity_base:
            raise InventoryError(
                (
                    f'Cannot cancel purchase; insufficient remaining stock for '
                    f'{item.name}. Available: {item.quantity_on_hand} {item.default_unit}, '
                    f'needed to reverse: {line.quantity_base} {item.default_unit}.'
                ),
                code='CANCEL_BLOCKED_STOCK_CONSUMED',
            )

    try:
        reversal_txn = credit_for_inventory_purchase_reversal(
            locked.total_amount,
            purchase_public_id=locked.public_id,
            actor_admin=actor_admin,
            note=reason or locked.note,
            reason=reason or f'Inventory purchase cancelled {locked.public_id}',
        )
    except AdminWalletError as exc:
        raise InventoryError(str(exc), code=getattr(exc, 'code', 'ADMIN_WALLET_ERROR')) from exc

    for line in lines:
        apply_stock_movement(
            line.item,
            movement_type=InventoryStockMovement.Type.PURCHASE_REVERSAL,
            quantity_delta=-line.quantity_base,
            actor_admin=actor_admin,
            note=f'Cancel purchase {locked.public_id}',
            purchase=locked,
            purchase_line=line,
            reverse_wac_cost=line.unit_cost,
        )

    locked.status = InventoryPurchase.Status.CANCELLED
    locked.cancelled_by = actor_admin
    locked.cancelled_at = timezone.now()
    locked.reversal_wallet_transaction = reversal_txn
    locked.save(
        update_fields=[
            'status',
            'cancelled_by',
            'cancelled_at',
            'reversal_wallet_transaction',
            'updated_at',
        ]
    )

    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.PURCHASE_CANCELLED,
        purchase=locked,
        previous_value={'status': InventoryPurchase.Status.CONFIRMED},
        new_value={
            'status': locked.status,
            'reversal_wallet_transaction_public_id': str(reversal_txn.public_id),
        },
        reference_id=str(locked.public_id),
        metadata={'reason': reason},
    )
    InventoryAuditLog.objects.create(
        actor_admin=actor_admin,
        action=InventoryAuditLog.Action.WALLET_REVERSED,
        purchase=locked,
        new_value={
            'amount': str(locked.total_amount),
            'wallet_transaction_public_id': str(reversal_txn.public_id),
        },
        reference_id=str(reversal_txn.public_id),
    )
    return locked
