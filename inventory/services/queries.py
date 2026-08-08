"""Inventory dashboard, histories, reports, and reconcile helpers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from inventory.models import (
    InventoryAuditLog,
    InventoryItem,
    InventoryKitchenUsage,
    InventoryPurchase,
    InventoryStockMovement,
    InventoryWastage,
)
from inventory.services.ledger import inventory_value, ledger_sum

ALLOWED_PURCHASE_FILTERS = {
    'date_from',
    'date_to',
    'item',
    'admin',
    'category',
    'amount_min',
    'amount_max',
    'supplier',
    'status',
    'q',
    'page',
    'page_size',
}

ALLOWED_USAGE_FILTERS = {
    'date_from',
    'date_to',
    'item',
    'admin',
    'q',
    'page',
    'page_size',
}

ALLOWED_AUDIT_FILTERS = {
    'date_from',
    'date_to',
    'action',
    'admin',
    'item',
    'page',
    'page_size',
}

ALLOWED_ITEM_FILTERS = {
    'status',
    'category',
    'q',
    'low_stock',
    'out_of_stock',
    'page',
    'page_size',
}

REPORT_KEYS = {
    'daily_purchase',
    'weekly_purchase',
    'monthly_purchase',
    'item_wise_purchase',
    'inventory_usage',
    'wastage',
    'stock_valuation',
    'admin_activity',
    'supplier_wise_purchase',
    'expense',
}


def _tz():
    return ZoneInfo(getattr(settings, 'TIME_ZONE', 'Asia/Dhaka'))


def _period_bounds_today():
    now = timezone.now().astimezone(_tz())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def _period_bounds_month():
    now = timezone.now().astimezone(_tz())
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    end = next_month - timedelta(microseconds=1)
    return start, end


def reject_unsupported_filters(params, allowed: set[str]) -> list[str]:
    return sorted(set(params.keys()) - allowed)


def dashboard_payload() -> dict:
    today_start, today_end = _period_bounds_today()
    month_start, month_end = _period_bounds_month()

    items = InventoryItem.objects.all()
    total_items = items.count()
    total_stock_value = sum((inventory_value(i) for i in items), Decimal('0.00'))

    confirmed = InventoryPurchase.objects.filter(
        status=InventoryPurchase.Status.CONFIRMED
    )
    today_purchases = confirmed.filter(
        confirmed_at__gte=today_start,
        confirmed_at__lte=today_end,
    )
    month_purchases = confirmed.filter(
        confirmed_at__gte=month_start,
        confirmed_at__lte=month_end,
    )

    low_stock_qs = [
        i
        for i in items.filter(status=InventoryItem.Status.ACTIVE)
        if i.is_low_stock
    ]
    out_stock_qs = list(
        items.filter(status=InventoryItem.Status.ACTIVE, quantity_on_hand__lte=0)
    )

    today_usage = InventoryKitchenUsage.objects.filter(
        created_at__gte=today_start,
        created_at__lte=today_end,
    )
    wastage_total = InventoryWastage.objects.aggregate(
        total=Sum('quantity_base')
    )['total'] or Decimal('0')

    return {
        'total_inventory_items': total_items,
        'total_stock_value': Decimal(total_stock_value).quantize(Decimal('0.01')),
        'today_purchases_count': today_purchases.count(),
        'today_purchases_amount': today_purchases.aggregate(total=Sum('total_amount'))[
            'total'
        ]
        or Decimal('0.00'),
        'month_purchase_cost': month_purchases.aggregate(total=Sum('total_amount'))[
            'total'
        ]
        or Decimal('0.00'),
        'low_stock_count': len(low_stock_qs),
        'out_of_stock_count': len(out_stock_qs),
        'today_kitchen_usage_count': today_usage.count(),
        'today_kitchen_usage_quantity': today_usage.aggregate(
            total=Sum('quantity_base')
        )['total']
        or Decimal('0'),
        'total_wastage_quantity': wastage_total,
        'low_stock_items': [
            {
                'public_id': i.public_id,
                'name': i.name,
                'quantity_on_hand': i.quantity_on_hand,
                'default_unit': i.default_unit,
                'minimum_stock_level': i.minimum_stock_level,
            }
            for i in low_stock_qs[:20]
        ],
        'out_of_stock_items': [
            {
                'public_id': i.public_id,
                'name': i.name,
                'quantity_on_hand': i.quantity_on_hand,
                'default_unit': i.default_unit,
            }
            for i in out_stock_qs[:20]
        ],
    }


def filter_items(queryset, params):
    unsupported = reject_unsupported_filters(params, ALLOWED_ITEM_FILTERS)
    if unsupported:
        raise ValueError(f'Unsupported filters: {", ".join(unsupported)}')

    status = params.get('status')
    if status:
        queryset = queryset.filter(status=status)
    category = params.get('category')
    if category:
        queryset = queryset.filter(category__iexact=category)
    q = params.get('q')
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(category__icontains=q)
        )

    # low/out evaluated in Python for derived signals when requested
    low = params.get('low_stock')
    out = params.get('out_of_stock')
    if low in ('1', 'true', 'True') or out in ('1', 'true', 'True'):
        items = list(queryset)
        if low in ('1', 'true', 'True'):
            items = [i for i in items if i.is_low_stock]
        if out in ('1', 'true', 'True'):
            items = [i for i in items if i.is_out_of_stock]
        ids = [i.pk for i in items]
        queryset = queryset.model.objects.filter(pk__in=ids).order_by('name')
    return queryset


def filter_purchases(queryset, params):
    unsupported = reject_unsupported_filters(params, ALLOWED_PURCHASE_FILTERS)
    if unsupported:
        raise ValueError(f'Unsupported filters: {", ".join(unsupported)}')

    date_from = params.get('date_from')
    date_to = params.get('date_to')
    if date_from:
        queryset = queryset.filter(
            Q(purchase_date__gte=date_from) | Q(created_at__date__gte=date_from)
        )
    if date_to:
        queryset = queryset.filter(
            Q(purchase_date__lte=date_to) | Q(created_at__date__lte=date_to)
        )
    item = params.get('item')
    if item:
        queryset = queryset.filter(lines__item__public_id=item).distinct()
    admin = params.get('admin')
    if admin:
        queryset = queryset.filter(
            Q(created_by_id=admin) | Q(created_by__user__email__iexact=admin)
        )
    category = params.get('category')
    if category:
        queryset = queryset.filter(lines__item__category__iexact=category).distinct()
    amount_min = params.get('amount_min')
    if amount_min:
        queryset = queryset.filter(total_amount__gte=amount_min)
    amount_max = params.get('amount_max')
    if amount_max:
        queryset = queryset.filter(total_amount__lte=amount_max)
    supplier = params.get('supplier')
    if supplier:
        queryset = queryset.filter(supplier__icontains=supplier)
    status = params.get('status')
    if status:
        queryset = queryset.filter(status=status)
    q = params.get('q')
    if q:
        queryset = queryset.filter(
            Q(supplier__icontains=q)
            | Q(note__icontains=q)
            | Q(lines__item__name__icontains=q)
        ).distinct()
    return queryset


def filter_usages(queryset, params):
    unsupported = reject_unsupported_filters(params, ALLOWED_USAGE_FILTERS)
    if unsupported:
        raise ValueError(f'Unsupported filters: {", ".join(unsupported)}')

    date_from = params.get('date_from')
    date_to = params.get('date_to')
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    item = params.get('item')
    if item:
        queryset = queryset.filter(item__public_id=item)
    admin = params.get('admin')
    if admin:
        queryset = queryset.filter(
            Q(issued_by_id=admin) | Q(issued_by__user__email__iexact=admin)
        )
    q = params.get('q')
    if q:
        queryset = queryset.filter(
            Q(purpose__icontains=q)
            | Q(note__icontains=q)
            | Q(item__name__icontains=q)
            | Q(menu_reference__icontains=q)
        )
    return queryset


def filter_audit_logs(queryset, params):
    unsupported = reject_unsupported_filters(params, ALLOWED_AUDIT_FILTERS)
    if unsupported:
        raise ValueError(f'Unsupported filters: {", ".join(unsupported)}')
    date_from = params.get('date_from')
    date_to = params.get('date_to')
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    action = params.get('action')
    if action:
        queryset = queryset.filter(action=action)
    admin = params.get('admin')
    if admin:
        queryset = queryset.filter(
            Q(actor_admin_id=admin) | Q(actor_admin__user__email__iexact=admin)
        )
    item = params.get('item')
    if item:
        queryset = queryset.filter(item__public_id=item)
    return queryset


def report_rows(report_key: str, params=None) -> list[dict]:
    params = params or {}
    if report_key not in REPORT_KEYS:
        raise ValueError(f'Unsupported report key: {report_key}')

    if report_key in {
        'daily_purchase',
        'weekly_purchase',
        'monthly_purchase',
        'item_wise_purchase',
        'supplier_wise_purchase',
        'expense',
    }:
        qs = InventoryPurchase.objects.filter(
            status=InventoryPurchase.Status.CONFIRMED
        ).prefetch_related('lines__item')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from:
            qs = qs.filter(confirmed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(confirmed_at__date__lte=date_to)
        rows = []
        for p in qs.order_by('-confirmed_at')[:500]:
            for line in p.lines.all():
                rows.append(
                    {
                        'purchase_public_id': str(p.public_id),
                        'date': (
                            p.confirmed_at.date().isoformat()
                            if p.confirmed_at
                            else None
                        ),
                        'item': line.item.name,
                        'quantity': str(line.quantity_base),
                        'unit': line.item.default_unit,
                        'line_total': str(line.line_total),
                        'supplier': p.supplier,
                        'total_amount': str(p.total_amount),
                        'wallet_transaction_public_id': (
                            str(p.wallet_transaction.public_id)
                            if p.wallet_transaction_id
                            else None
                        ),
                    }
                )
        return rows

    if report_key == 'inventory_usage':
        qs = InventoryKitchenUsage.objects.select_related('item', 'issued_by')
        return [
            {
                'public_id': str(u.public_id),
                'date': u.created_at.date().isoformat(),
                'item': u.item.name,
                'quantity': str(u.quantity_base),
                'unit': u.item.default_unit,
                'purpose': u.purpose,
                'issued_by': (
                    u.issued_by.user.get_full_name() if u.issued_by_id else None
                ),
            }
            for u in qs.order_by('-created_at')[:500]
        ]

    if report_key == 'wastage':
        qs = InventoryWastage.objects.select_related('item')
        return [
            {
                'public_id': str(w.public_id),
                'date': w.created_at.date().isoformat(),
                'item': w.item.name,
                'quantity': str(w.quantity_base),
                'reason': w.reason,
            }
            for w in qs.order_by('-created_at')[:500]
        ]

    if report_key == 'stock_valuation':
        return [
            {
                'public_id': str(i.public_id),
                'name': i.name,
                'quantity_on_hand': str(i.quantity_on_hand),
                'unit': i.default_unit,
                'average_unit_cost': (
                    str(i.average_unit_cost) if i.average_unit_cost is not None else None
                ),
                'stock_value': str(inventory_value(i)),
            }
            for i in InventoryItem.objects.order_by('name')
        ]

    if report_key == 'admin_activity':
        qs = InventoryAuditLog.objects.select_related('actor_admin')
        return [
            {
                'action': a.action,
                'admin': (
                    a.actor_admin.user.get_full_name() if a.actor_admin_id else None
                ),
                'reference_id': a.reference_id,
                'created_at': a.created_at.isoformat(),
            }
            for a in qs.order_by('-created_at')[:500]
        ]

    return []


def reconcile_items() -> list[dict]:
    drift = []
    for item in InventoryItem.objects.all():
        summed = ledger_sum(item)
        if summed != item.quantity_on_hand:
            drift.append(
                {
                    'public_id': str(item.public_id),
                    'name': item.name,
                    'quantity_on_hand': str(item.quantity_on_hand),
                    'ledger_sum': str(summed),
                }
            )
    return drift


def item_history_summary(item: InventoryItem) -> dict:
    movements = item.movements.all()
    purchased = movements.filter(
        type=InventoryStockMovement.Type.PURCHASE
    ).aggregate(total=Sum('quantity_delta'))['total'] or Decimal('0')
    used = movements.filter(
        type=InventoryStockMovement.Type.KITCHEN_USAGE
    ).aggregate(total=Sum('quantity_delta'))['total'] or Decimal('0')
    adjusted = movements.filter(
        type=InventoryStockMovement.Type.ADJUSTMENT
    ).aggregate(total=Sum('quantity_delta'))['total'] or Decimal('0')
    purchase_cost = (
        InventoryPurchase.objects.filter(
            status=InventoryPurchase.Status.CONFIRMED,
            lines__item=item,
        )
        .distinct()
        .aggregate(total=Sum('lines__line_total'))['total']
        or Decimal('0.00')
    )
    return {
        'opening_stock': '0.000',
        'purchased_quantity': str(purchased),
        'used_quantity': str(abs(used)),
        'adjusted_quantity': str(adjusted),
        'current_stock': str(item.quantity_on_hand),
        'total_purchase_cost': str(purchase_cost),
        'average_unit_cost': (
            str(item.average_unit_cost) if item.average_unit_cost is not None else None
        ),
        'stock_value': str(inventory_value(item)),
        **{
            'out_of_stock': item.is_out_of_stock,
            'low_stock': item.is_low_stock,
        },
    }
