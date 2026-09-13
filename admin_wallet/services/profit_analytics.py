"""Admin Profit analytics from persisted MealProfitTransaction ledger."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

from admin_wallet.models import MealProfitTransaction

_MONEY = Decimal('0.01')
_ZERO = Decimal('0.00')

ALLOWED_HISTORY_FILTERS = frozenset(
    {
        'start_date',
        'end_date',
        'package',
        'customer',
        'meal_period',
        'page',
        'page_size',
    }
)


def _tz():
    return ZoneInfo(getattr(settings, 'TIME_ZONE', 'Asia/Dhaka'))


def _quantize(value) -> Decimal:
    if value is None:
        return _ZERO
    return Decimal(value).quantize(_MONEY)


def _period_bounds_today_dates() -> tuple[date, date]:
    now = timezone.now().astimezone(_tz())
    d = now.date()
    return d, d


def _period_bounds_month_dates() -> tuple[date, date]:
    now = timezone.now().astimezone(_tz())
    start = now.date().replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Invalid date; use YYYY-MM-DD.') from exc


def ledger_qs(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    package_public_id: str | None = None,
    customer_public_id: str | None = None,
    meal_period: str | None = None,
):
    qs = MealProfitTransaction.objects.select_related(
        'package',
        'customer__user',
        'order_delivery',
    )
    if start_date is not None:
        qs = qs.filter(service_date__gte=start_date)
    if end_date is not None:
        qs = qs.filter(service_date__lte=end_date)
    if package_public_id:
        qs = qs.filter(package__public_id=package_public_id)
    if customer_public_id:
        qs = qs.filter(customer__public_id=customer_public_id)
    if meal_period:
        qs = qs.filter(meal_period=meal_period)
    return qs


def sum_profit(qs) -> Decimal:
    return _quantize(qs.aggregate(total=Sum('profit_amount'))['total'])


def sum_revenue(qs) -> Decimal:
    return _quantize(qs.aggregate(total=Sum('meal_price'))['total'])


def sum_food_cost(qs) -> Decimal:
    return _quantize(qs.aggregate(total=Sum('food_cost'))['total'])


def package_breakdown(qs) -> list[dict]:
    rows = (
        qs.values('package__public_id', 'package__meal_name', 'package_name_snapshot')
        .annotate(
            charged_deliveries=Count('id'),
            revenue=Sum('meal_price'),
            food_cost=Sum('food_cost'),
            profit=Sum('profit_amount'),
        )
        .order_by()
    )
    result = []
    for row in rows:
        name = row['package_name_snapshot'] or row['package__meal_name'] or ''
        result.append(
            {
                'package_public_id': row['package__public_id'],
                'package_name': name,
                'charged_deliveries': row['charged_deliveries'],
                'revenue': _quantize(row['revenue']),
                'food_cost': _quantize(row['food_cost']),
                'profit': _quantize(row['profit']),
            }
        )
    result.sort(key=lambda r: (-r['profit'], r['package_name'] or ''))
    return result


def meal_period_breakdown(qs) -> list[dict]:
    total_profit = sum_profit(qs)
    rows = (
        qs.values('meal_period')
        .annotate(
            charged_deliveries=Count('id'),
            revenue=Sum('meal_price'),
            food_cost=Sum('food_cost'),
            profit=Sum('profit_amount'),
        )
        .order_by('meal_period')
    )
    result = []
    for row in rows:
        profit = _quantize(row['profit'])
        if total_profit > 0:
            share = _quantize((profit / total_profit) * Decimal('100'))
        else:
            share = _ZERO
        result.append(
            {
                'meal_period': row['meal_period'],
                'charged_deliveries': row['charged_deliveries'],
                'revenue': _quantize(row['revenue']),
                'food_cost': _quantize(row['food_cost']),
                'profit': profit,
                'profit_share_percent': share,
            }
        )
    return result


def customer_breakdown(qs, *, limit: int = 50) -> list[dict]:
    rows = (
        qs.values('customer__public_id', 'customer__user__email')
        .annotate(
            charged_deliveries=Count('id'),
            revenue=Sum('meal_price'),
            food_cost=Sum('food_cost'),
            profit=Sum('profit_amount'),
        )
        .order_by()
    )
    result = []
    for row in rows:
        result.append(
            {
                'customer_public_id': row['customer__public_id'],
                'customer_email': row['customer__user__email'] or '',
                'charged_deliveries': row['charged_deliveries'],
                'revenue': _quantize(row['revenue']),
                'food_cost': _quantize(row['food_cost']),
                'profit': _quantize(row['profit']),
            }
        )
    result.sort(key=lambda r: (-r['profit'], r['customer_email'] or ''))
    return result[:limit]


def daily_profit_chart(qs) -> list[dict]:
    rows = (
        qs.values('service_date')
        .annotate(
            profit=Sum('profit_amount'),
            revenue=Sum('meal_price'),
            food_cost=Sum('food_cost'),
            charged_deliveries=Count('id'),
        )
        .order_by('service_date')
    )
    return [
        {
            'date': row['service_date'].isoformat(),
            'profit': _quantize(row['profit']),
            'revenue': _quantize(row['revenue']),
            'food_cost': _quantize(row['food_cost']),
            'charged_deliveries': row['charged_deliveries'],
        }
        for row in rows
    ]


def dashboard_payload(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    package_public_id: str | None = None,
    customer_public_id: str | None = None,
    meal_period: str | None = None,
) -> dict:
    """
    Ledger-only dashboard aggregates.

    Default chart/range window is the current calendar month (service_date).
    Optional start_date/end_date override the range totals and chart window;
    lifetime/month/today cards remain calendar-scoped unless a custom range
    is supplied — when custom range is set, ``range_profit`` is also returned.
    """
    today_start, today_end = _period_bounds_today_dates()
    month_start, month_end = _period_bounds_month_dates()

    base = ledger_qs(
        package_public_id=package_public_id,
        customer_public_id=customer_public_id,
        meal_period=meal_period,
    )
    lifetime_qs = base
    month_qs = base.filter(service_date__gte=month_start, service_date__lte=month_end)
    today_qs = base.filter(service_date__gte=today_start, service_date__lte=today_end)

    chart_start = start_date or month_start
    chart_end = end_date or month_end
    range_qs = base.filter(service_date__gte=chart_start, service_date__lte=chart_end)

    payload = {
        'lifetime_profit': sum_profit(lifetime_qs),
        'month_profit': sum_profit(month_qs),
        'today_profit': sum_profit(today_qs),
        'range_start': chart_start.isoformat(),
        'range_end': chart_end.isoformat(),
        'range_profit': sum_profit(range_qs),
        'range_revenue': sum_revenue(range_qs),
        'range_food_cost': sum_food_cost(range_qs),
        'range_deliveries': range_qs.count(),
        'profit_by_package': package_breakdown(range_qs),
        'profit_by_meal_period': meal_period_breakdown(range_qs),
        'profit_by_customer': customer_breakdown(range_qs),
        'daily_profit_chart': daily_profit_chart(range_qs),
    }
    return payload


def filter_history(params: dict):
    """Validate allowlisted filters and return queryset. Raises ValueError on bad input."""
    unknown = set(params.keys()) - ALLOWED_HISTORY_FILTERS
    if unknown:
        raise ValueError(f'Unsupported filter(s): {", ".join(sorted(unknown))}')

    start_date = _parse_date(params.get('start_date'))
    end_date = _parse_date(params.get('end_date'))
    meal_period = params.get('meal_period') or None
    if meal_period and meal_period not in ('lunch', 'dinner'):
        raise ValueError('meal_period must be lunch or dinner.')

    return ledger_qs(
        start_date=start_date,
        end_date=end_date,
        package_public_id=params.get('package') or None,
        customer_public_id=params.get('customer') or None,
        meal_period=meal_period,
    ).order_by('-service_date', '-created_at', '-id')
