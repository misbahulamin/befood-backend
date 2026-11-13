"""Per-customer 360 analytics aggregations (no Request objects)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import Coalesce, ExtractIsoWeekDay
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import OrderDelivery
from orders.services.customer_lifecycle import (
    business_calendar_today,
    month_bounds_dhaka,
    to_business_date,
)
from orders.services.meal_off import CUTOFF_PASSED_NOTE
from user_management.models import CustomerProfile
from user_management.services.admin_customer import (
    customer_delivery_scope,
    reject_unknown_query_params,
)
from wallet.models import WalletTransaction

BUSINESS_TZ = ZoneInfo('Asia/Dhaka')
BUSINESS_TZ_NAME = 'Asia/Dhaka'

ANALYTICS_QUERY_ALLOWLIST = frozenset({'from', 'to'})
TOP_N = 8
RECENT_RECHARGES = 5
BLOCKED_ESTIMATE_NOTE = 'estimate_from_system_cutoff_skips_and_current_block'
WALLET_RECHARGE_NOTE = (
    'after_block classification uses current blocked_at and system cutoff skips; '
    'no historical block-event ledger'
)

MONEY = Decimal('0.01')

WEEKDAY_KEYS = {
    1: 'monday',
    2: 'tuesday',
    3: 'wednesday',
    4: 'thursday',
    5: 'friday',
    6: 'saturday',
    7: 'sunday',
}


def _money(value: Decimal | int | float | None) -> str:
    amount = Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)
    return f'{amount:.2f}'


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 4)


def _parse_optional_date(raw, field: str) -> date | None:
    if raw is None or raw == '':
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    parsed = parse_date(str(raw).strip())
    if parsed is None:
        raise ValidationError({field: ['Invalid date. Use YYYY-MM-DD.']})
    return parsed


def parse_analytics_window(params) -> tuple[date, date, str]:
    """
    Resolve inclusive Asia/Dhaka window from allowlisted from/to.

    Defaults to the current Dhaka calendar month when both are omitted.
    """
    reject_unknown_query_params(params, ANALYTICS_QUERY_ALLOWLIST)
    start = _parse_optional_date(params.get('from'), 'from')
    end = _parse_optional_date(params.get('to'), 'to')

    if start is None and end is None:
        start, end = month_bounds_dhaka()
        label = f'{start.isoformat()}..{end.isoformat()} (current_month)'
        return start, end, label

    if start is None or end is None:
        raise ValidationError({'from': ['Both from and to (YYYY-MM-DD) are required.']})
    if end < start:
        raise ValidationError({'to': ['to must be on or after from.']})
    if (end - start).days > 366:
        raise ValidationError({'to': ['Date range cannot exceed 366 days.']})
    return start, end, f'{start.isoformat()}..{end.isoformat()}'


def customer_deliveries_qs(customer: CustomerProfile):
    return OrderDelivery.objects.filter(customer_delivery_scope(customer))


def _window_q(start: date, end: date) -> Q:
    return Q(service_date__gte=start, service_date__lte=end)


def _package_name_annotation():
    return Coalesce(
        F('order__meal_name_snapshot'),
        F('subscription__meal_name_snapshot'),
    )


def _meal_type_annotation():
    return Coalesce(
        F('order__meal__meal_type'),
        F('subscription__meal__meal_type'),
    )


def _meal_id_annotation():
    return Coalesce(F('order__meal_id'), F('subscription__meal_id'))


def _count_rows(qs) -> int:
    return qs.count()


def _named_count_rows(qs, *, key_field: str, label_field: str | None = None) -> list[dict[str, Any]]:
    rows = (
        qs.values(key_field)
        .annotate(count=Count('id'))
        .order_by('-count', key_field)
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        key = row[key_field]
        if key is None or key == '':
            continue
        item: dict[str, Any] = {
            'key': str(key),
            'label': str(key) if label_field is None else str(row.get(label_field) or key),
            'count': int(row['count']),
        }
        out.append(item)
    return out


def _top_named_counts(qs, *, name_expr, limit: int = TOP_N) -> list[dict[str, Any]]:
    rows = (
        qs.annotate(_name=name_expr)
        .exclude(_name__isnull=True)
        .exclude(_name='')
        .values('_name')
        .annotate(count=Count('id'))
        .order_by('-count', '_name')[:limit]
    )
    return [
        {'key': row['_name'], 'label': row['_name'], 'count': int(row['count'])}
        for row in rows
    ]


def build_consumption_section(customer: CustomerProfile, start: date, end: date) -> dict[str, Any]:
    base = customer_deliveries_qs(customer).filter(
        status=OrderDelivery.DeliveryStatus.DELIVERED
    )
    window = base.filter(_window_q(start, end))
    by_period = _named_count_rows(window, key_field='meal_period')
    by_type_rows = (
        window.annotate(_meal_type=_meal_type_annotation())
        .exclude(_meal_type__isnull=True)
        .exclude(_meal_type='')
        .values('_meal_type')
        .annotate(count=Count('id'))
        .order_by('-count', '_meal_type')
    )
    by_meal_type = [
        {
            'key': row['_meal_type'],
            'label': row['_meal_type'],
            'count': int(row['count']),
        }
        for row in by_type_rows
    ]
    return {
        'lifetime_total': _count_rows(base),
        'window_total': _count_rows(window),
        'by_meal_period': by_period,
        'by_meal_type': by_meal_type,
        'top_meals': _top_named_counts(window, name_expr=_package_name_annotation()),
    }


def build_meal_off_section(customer: CustomerProfile, start: date, end: date) -> dict[str, Any]:
    preference = customer_deliveries_qs(customer).filter(
        status=OrderDelivery.DeliveryStatus.SKIPPED,
        skip_source=OrderDelivery.SkipSource.CUSTOMER,
    )
    window = preference.filter(_window_q(start, end))

    weekday_rows = (
        window.annotate(weekday=ExtractIsoWeekDay('service_date'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    by_weekday = [
        {
            'key': WEEKDAY_KEYS.get(int(row['weekday']), str(row['weekday'])),
            'label': WEEKDAY_KEYS.get(int(row['weekday']), str(row['weekday'])),
            'count': int(row['count']),
        }
        for row in weekday_rows
        if row['weekday'] is not None
    ]

    return {
        'lifetime_total': _count_rows(preference),
        'window_total': _count_rows(window),
        'by_meal_period': _named_count_rows(window, key_field='meal_period'),
        'by_weekday': by_weekday,
        'top_off_meals_lifetime': _top_named_counts(
            preference, name_expr=_package_name_annotation()
        ),
        'top_off_meals_window': _top_named_counts(
            window, name_expr=_package_name_annotation()
        ),
        'top_off_menus_window': _build_top_off_menus_window(window),
    }


def _build_top_off_menus_window(window_qs) -> list[dict[str, Any]]:
    """
    Aggregate preference skips by meal/date/period, resolve published slots
    in a bounded loop, fall back to package name when unresolved.
    """
    grouped = (
        window_qs.annotate(
            meal_id=_meal_id_annotation(),
            package_name=_package_name_annotation(),
        )
        .values('meal_id', 'service_date', 'meal_period', 'package_name')
        .annotate(count=Count('id'))
        .order_by('-count', 'service_date', 'meal_period')
    )

    tallies: dict[str, dict[str, Any]] = {}
    for row in grouped:
        count = int(row['count'])
        meal_id = row['meal_id']
        service_date = row['service_date']
        meal_period = row['meal_period']
        package_name = row['package_name'] or 'Unknown package'

        slot = None
        if meal_id is not None:
            try:
                slot = resolve_published_slot_for_delivery(
                    meal_id=int(meal_id),
                    service_date=service_date,
                    meal_period=meal_period,
                )
            except Exception:
                slot = None

        if slot is not None:
            ingredients = list(
                slot.items.select_related('ingredient')
                .order_by('ingredient__name')
                .values_list('ingredient__name', flat=True)[:6]
            )
            menu_label = ', '.join(ingredients) if ingredients else package_name
            key = f'slot:{slot.pk}'
            label = f'{menu_label} ({service_date.isoformat()} {meal_period})'
        else:
            key = f'package:{package_name}|{service_date.isoformat()}|{meal_period}'
            label = f'{package_name} ({service_date.isoformat()} {meal_period})'

        existing = tallies.get(key)
        if existing is None:
            tallies[key] = {'key': key, 'label': label, 'count': count}
        else:
            existing['count'] += count

    ranked = sorted(tallies.values(), key=lambda item: (-item['count'], item['label']))
    return ranked[:TOP_N]


def build_blocked_low_balance_section(
    customer: CustomerProfile, start: date, end: date
) -> dict[str, Any]:
    system_cutoff = customer_deliveries_qs(customer).filter(
        status=OrderDelivery.DeliveryStatus.SKIPPED,
        skip_source=OrderDelivery.SkipSource.SYSTEM,
        note=CUTOFF_PASSED_NOTE,
    )
    lifetime_estimate = _count_rows(system_cutoff)
    window_estimate = _count_rows(system_cutoff.filter(_window_q(start, end)))

    currently_blocked = bool(customer.meal_service_blocked_low_balance)
    blocked_at = customer.meal_service_blocked_at
    if currently_blocked and blocked_at is not None:
        blocked_from = to_business_date(blocked_at)
        if blocked_from is not None:
            # Project remaining scheduled slots while currently blocked in-window.
            projected = customer_deliveries_qs(customer).filter(
                status=OrderDelivery.DeliveryStatus.SCHEDULED,
                service_date__gte=max(blocked_from, start),
                service_date__lte=end,
            ).count()
            window_estimate += projected

    return {
        'currently_blocked': currently_blocked,
        'blocked_at': blocked_at.isoformat() if blocked_at else None,
        'blocked_meals_estimate': lifetime_estimate,
        'blocked_meals_window_estimate': window_estimate,
        'note': BLOCKED_ESTIMATE_NOTE,
    }


def _recharge_event_time(txn: WalletTransaction) -> datetime:
    return txn.reviewed_at or txn.created_at


def _recharge_business_date(txn: WalletTransaction) -> date | None:
    return to_business_date(_recharge_event_time(txn))


def build_wallet_recharge_section(
    customer: CustomerProfile, start: date, end: date
) -> dict[str, Any]:
    wallet = getattr(customer, 'wallet', None)
    empty = {
        'recharge_count': 0,
        'total_recharged': '0.00',
        'average_amount': None,
        'last_recharge_at': None,
        'on_time_count': 0,
        'recharges_after_block_count': 0,
        'median_gap_days': None,
        'by_method': [],
        'recent': [],
        'note': WALLET_RECHARGE_NOTE,
    }
    if wallet is None:
        return empty

    completed = list(
        WalletTransaction.objects.filter(
            wallet=wallet,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            status=WalletTransaction.Status.COMPLETED,
        ).order_by('created_at', 'id')
    )
    if not completed:
        return empty

    total = sum((txn.amount for txn in completed), Decimal('0.00'))
    avg = (total / Decimal(len(completed))).quantize(MONEY, rounding=ROUND_HALF_UP)

    method_counts: dict[str, int] = defaultdict(int)
    for txn in completed:
        method_counts[txn.method or 'unknown'] += 1
    by_method = [
        {'key': key, 'label': key, 'count': count}
        for key, count in sorted(method_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    gaps: list[int] = []
    for prev, curr in zip(completed, completed[1:]):
        prev_d = _recharge_business_date(prev)
        curr_d = _recharge_business_date(curr)
        if prev_d is not None and curr_d is not None:
            gaps.append((curr_d - prev_d).days)
    median_gap = float(median(gaps)) if gaps else None

    # After-block signals: current blocked_at and system cutoff skip dates.
    block_start = (
        to_business_date(customer.meal_service_blocked_at)
        if customer.meal_service_blocked_at
        else None
    )
    cutoff_dates = set(
        customer_deliveries_qs(customer)
        .filter(
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.SYSTEM,
            note=CUTOFF_PASSED_NOTE,
        )
        .values_list('service_date', flat=True)
        .distinct()
    )

    after_block = 0
    for txn in completed:
        txn_date = _recharge_business_date(txn)
        if txn_date is None:
            continue
        after_current_block = (
            customer.meal_service_blocked_low_balance
            and block_start is not None
            and txn_date >= block_start
        )
        after_cutoff = any(
            0 <= (txn_date - skip_date).days <= 7 for skip_date in cutoff_dates
        )
        if after_current_block or after_cutoff:
            after_block += 1

    on_time = max(0, len(completed) - after_block)
    last = completed[-1]
    recent = [
        {
            'public_id': str(txn.public_id),
            'amount': _money(txn.amount),
            'method': txn.method,
            'created_at': txn.created_at.isoformat() if txn.created_at else None,
            'reviewed_at': txn.reviewed_at.isoformat() if txn.reviewed_at else None,
        }
        for txn in reversed(completed[-RECENT_RECHARGES:])
    ]

    return {
        'recharge_count': len(completed),
        'total_recharged': _money(total),
        'average_amount': _money(avg),
        'last_recharge_at': _recharge_event_time(last).isoformat(),
        'on_time_count': on_time,
        'recharges_after_block_count': after_block,
        'median_gap_days': median_gap,
        'by_method': by_method,
        'recent': recent,
        'note': WALLET_RECHARGE_NOTE,
    }


def build_matrix_section(
    *,
    consumption: dict[str, Any],
    meal_off: dict[str, Any],
    blocked: dict[str, Any],
    wallet_recharge: dict[str, Any],
    start: date,
    end: date,
    customer: CustomerProfile,
) -> dict[str, Any]:
    delivered = int(consumption.get('window_total') or 0)
    preference_offs = int(meal_off.get('window_total') or 0)
    blocked_est = int(blocked.get('blocked_meals_window_estimate') or 0)

    # Opportunity ≈ delivered + preference offs + blocked estimates in window.
    opportunity = delivered + preference_offs + blocked_est
    delivery_rate = _ratio(delivered, opportunity)
    preference_off_rate = _ratio(preference_offs, delivered + preference_offs)
    block_rate_estimate = _ratio(blocked_est, delivered + blocked_est)

    window_days = (end - start).days + 1
    recharges_in_window = 0
    wallet = getattr(customer, 'wallet', None)
    if wallet is not None and window_days > 0:
        # Count completed recharges whose business date falls in window.
        for txn in WalletTransaction.objects.filter(
            wallet=wallet,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            status=WalletTransaction.Status.COMPLETED,
        ).only('created_at', 'reviewed_at'):
            txn_date = _recharge_business_date(txn)
            if txn_date is not None and start <= txn_date <= end:
                recharges_in_window += 1
        recharges_per_30d = round((recharges_in_window / window_days) * 30, 4)
    else:
        recharges_per_30d = None if window_days <= 0 else 0.0

    # If never recharged and zero window activity, keep 0.0 only when window is valid.
    if wallet is None:
        recharges_per_30d = None if window_days <= 0 else 0.0

    return {
        'delivery_rate': delivery_rate,
        'preference_off_rate': preference_off_rate,
        'block_rate_estimate': block_rate_estimate,
        'recharges_per_30d': recharges_per_30d,
    }


def build_customer_analytics(customer: CustomerProfile, params) -> dict[str, Any]:
    start, end, label = parse_analytics_window(params)
    consumption = build_consumption_section(customer, start, end)
    meal_off = build_meal_off_section(customer, start, end)
    blocked = build_blocked_low_balance_section(customer, start, end)
    wallet_recharge = build_wallet_recharge_section(customer, start, end)
    matrix = build_matrix_section(
        consumption=consumption,
        meal_off=meal_off,
        blocked=blocked,
        wallet_recharge=wallet_recharge,
        start=start,
        end=end,
        customer=customer,
    )
    return {
        'generated_at': timezone.now().isoformat(),
        'timezone': BUSINESS_TZ_NAME,
        'window': {
            'from': start.isoformat(),
            'to': end.isoformat(),
            'label': label,
        },
        'consumption': consumption,
        'meal_off': meal_off,
        'blocked_low_balance': blocked,
        'wallet_recharge': wallet_recharge,
        'matrix': matrix,
    }
