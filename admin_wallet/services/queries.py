"""Admin Wallet summary and dashboard aggregates."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from admin_wallet.models import AdminWallet, AdminWalletTransaction
from admin_wallet.services.ledger import get_or_create_platform_wallet
from orders.models import OrderDelivery


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


def _sum_completed(qs, direction: str) -> Decimal:
    total = (
        qs.filter(
            status=AdminWalletTransaction.Status.COMPLETED,
            direction=direction,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )
    return Decimal(total).quantize(Decimal('0.01'))


def meal_revenue_recognized(*, start: datetime | None = None, end: datetime | None = None) -> Decimal:
    """
    Sum charged meal-delivery amounts (revenue recognition).

    Not funded from Admin Wallet cash credits — custody is credited on recharge.
    """
    qs = OrderDelivery.objects.filter(
        payment_status=OrderDelivery.PaymentStatus.CHARGED,
        charged_amount__isnull=False,
    )
    if start is not None:
        qs = qs.filter(updated_at__gte=start)
    if end is not None:
        qs = qs.filter(updated_at__lte=end)
    total = qs.aggregate(total=Sum('charged_amount'))['total'] or Decimal('0.00')
    return Decimal(total).quantize(Decimal('0.01'))


def wallet_summary(wallet: AdminWallet | None = None) -> dict:
    wallet = wallet or get_or_create_platform_wallet()
    return {
        'public_id': wallet.public_id,
        'balance': wallet.balance,
        'currency': wallet.currency,
        'status': wallet.status,
        'total_received': wallet.total_received,
        'total_manual_added': wallet.total_manual_added,
        'total_withdrawn': wallet.total_withdrawn,
        'total_expenses': wallet.total_expenses,
        # Meal revenue from charged deliveries (not funding credits / legacy counter).
        'total_customer_payments': meal_revenue_recognized(),
        'total_customer_funding': wallet.total_customer_funding,
        'total_customer_withdrawals': wallet.total_customer_withdrawals,
        'updated_at': wallet.updated_at,
        'created_at': wallet.created_at,
    }


def period_totals(wallet: AdminWallet, start: datetime, end: datetime) -> dict:
    qs = AdminWalletTransaction.objects.filter(
        wallet=wallet,
        created_at__gte=start,
        created_at__lte=end,
    )
    return {
        'income': _sum_completed(qs, AdminWalletTransaction.Direction.CREDIT),
        'expense': _sum_completed(qs, AdminWalletTransaction.Direction.DEBIT),
        'meal_revenue': meal_revenue_recognized(start=start, end=end),
    }


def dashboard_payload(*, recent_limit: int = 10) -> dict:
    wallet = get_or_create_platform_wallet()
    today_start, today_end = _period_bounds_today()
    month_start, month_end = _period_bounds_month()
    today = period_totals(wallet, today_start, today_end)
    month = period_totals(wallet, month_start, month_end)
    recent = list(
        AdminWalletTransaction.objects.filter(wallet=wallet)
        .select_related(
            'order',
            'order_delivery',
            'customer__user',
            'actor_admin__user',
        )
        .order_by('-created_at', '-id')[:recent_limit]
    )
    return {
        'wallet': wallet_summary(wallet),
        'today_income': today['income'],
        'today_expense': today['expense'],
        'month_revenue': month['income'],
        'month_expense': month['expense'],
        'total_customer_payments': meal_revenue_recognized(),
        'total_customer_funding': wallet.total_customer_funding,
        'total_customer_withdrawals': wallet.total_customer_withdrawals,
        'total_withdrawn': wallet.total_withdrawn,
        'recent_transactions': recent,
    }


def reconcile_balance(wallet: AdminWallet | None = None) -> dict:
    """Compare denormalized balance to sum(credits) - sum(debits)."""
    wallet = wallet or get_or_create_platform_wallet()
    qs = AdminWalletTransaction.objects.filter(
        wallet=wallet,
        status=AdminWalletTransaction.Status.COMPLETED,
    )
    credits = _sum_completed(qs, AdminWalletTransaction.Direction.CREDIT)
    debits = _sum_completed(qs, AdminWalletTransaction.Direction.DEBIT)
    computed = (credits - debits).quantize(Decimal('0.01'))
    return {
        'stored_balance': wallet.balance,
        'computed_balance': computed,
        'matches': wallet.balance == computed,
        'total_credits': credits,
        'total_debits': debits,
    }


ALLOWED_TRANSACTION_FILTERS = frozenset(
    {
        'date_from',
        'date_to',
        'direction',
        'type',
        'method',
        'status',
        'q',
        'page',
        'page_size',
    }
)

TYPE_GROUPS = {
    'expense': sorted(AdminWalletTransaction.EXPENSE_TYPES),
    'refund': [AdminWalletTransaction.Type.CUSTOMER_REFUND],
}


def filter_transactions(wallet: AdminWallet, params: dict):
    """
    Apply allowlisted filters. Raises ValueError for unsupported keys/values.
    """
    unknown = set(params.keys()) - ALLOWED_TRANSACTION_FILTERS
    if unknown:
        raise ValueError(f'Unsupported filter(s): {", ".join(sorted(unknown))}')

    qs = AdminWalletTransaction.objects.filter(wallet=wallet).select_related(
        'order',
        'order_delivery',
        'customer__user',
        'actor_admin__user',
    )

    direction = params.get('direction')
    if direction:
        if direction not in AdminWalletTransaction.Direction.values:
            raise ValueError('Invalid direction.')
        qs = qs.filter(direction=direction)

    txn_type = params.get('type')
    if txn_type:
        if txn_type in TYPE_GROUPS:
            qs = qs.filter(type__in=TYPE_GROUPS[txn_type])
        elif txn_type in AdminWalletTransaction.Type.values:
            qs = qs.filter(type=txn_type)
        else:
            raise ValueError('Invalid type.')

    method = params.get('method')
    if method:
        if method not in AdminWalletTransaction.Method.values:
            raise ValueError('Invalid method.')
        qs = qs.filter(method=method)

    status = params.get('status')
    if status:
        if status not in AdminWalletTransaction.Status.values:
            raise ValueError('Invalid status.')
        qs = qs.filter(status=status)

    date_from = params.get('date_from')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    date_to = params.get('date_to')
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    q = (params.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(public_id__icontains=q)
            | Q(reference__icontains=q)
            | Q(source__icontains=q)
            | Q(note__icontains=q)
            | Q(order__public_id__icontains=q)
            | Q(customer__user__email__icontains=q)
            | Q(customer__phone__icontains=q)
        )

    return qs.order_by('-created_at', '-id')
