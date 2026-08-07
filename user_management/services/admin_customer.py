"""Admin customer directory and history read helpers (no Request objects)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db.models import Count, Exists, OuterRef, Prefetch, Q, QuerySet, Sum
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from orders.models import Order, OrderDelivery, OrderStatusHistory
from user_management.models import CustomerAddress, CustomerProfile
from wallet.models import Wallet, WalletTransaction

LIST_QUERY_ALLOWLIST = frozenset(
    {
        'q',
        'is_active',
        'is_email_verified',
        'has_active_order',
        'meal_public_id',
        'package_id',
        'registered_from',
        'registered_to',
        'sort',
        'page',
        'page_size',
    }
)

MEAL_QUERY_ALLOWLIST = frozenset(
    {
        'status',
        'meal_period',
        'service_date_from',
        'service_date_to',
        'page',
        'page_size',
    }
)

SORT_ALLOWLIST = {
    'date_joined': ('user__date_joined', 'public_id'),
    '-date_joined': ('-user__date_joined', 'public_id'),
    'created_at': ('created_at', 'public_id'),
    '-created_at': ('-created_at', 'public_id'),
    'email': ('user__email', 'public_id'),
    '-email': ('-user__email', 'public_id'),
}

TRUE_VALUES = frozenset({'true', '1', 'yes'})
FALSE_VALUES = frozenset({'false', '0', 'no'})


def parse_bool_param(raw: str | None, *, field: str) -> bool | None:
    if raw is None or raw == '':
        return None
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValidationError({field: ['Must be a boolean (true/false).']})


def reject_unknown_query_params(query_params, allowlist: frozenset[str]) -> None:
    unknown = sorted(set(query_params.keys()) - allowlist)
    if unknown:
        raise ValidationError(
            {'query': [f'Unsupported query parameter(s): {", ".join(unknown)}.']}
        )


def customer_base_queryset() -> QuerySet[CustomerProfile]:
    return CustomerProfile.objects.select_related('user', 'wallet').prefetch_related(
        Prefetch(
            'addresses',
            queryset=CustomerAddress.objects.order_by('address_type', 'id'),
        ),
        Prefetch(
            'meal_orders',
            queryset=Order.objects.filter(order_status=Order.OrderStatus.ACTIVE)
            .select_related('meal')
            .order_by('-created_at', '-id'),
            to_attr='_prefetched_active_orders',
        ),
    )


def apply_customer_list_filters(queryset: QuerySet[CustomerProfile], params) -> QuerySet[CustomerProfile]:
    reject_unknown_query_params(params, LIST_QUERY_ALLOWLIST)

    q = (params.get('q') or '').strip()
    if q:
        queryset = queryset.filter(
            Q(user__email__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(phone__icontains=q)
        )

    is_active = parse_bool_param(params.get('is_active'), field='is_active')
    if is_active is not None:
        queryset = queryset.filter(user__is_active=is_active)

    is_email_verified = parse_bool_param(
        params.get('is_email_verified'), field='is_email_verified'
    )
    if is_email_verified is not None:
        queryset = queryset.filter(is_email_verified=is_email_verified)

    has_active_order = parse_bool_param(
        params.get('has_active_order'), field='has_active_order'
    )
    active_exists = Exists(
        Order.objects.filter(
            customer_id=OuterRef('pk'),
            order_status=Order.OrderStatus.ACTIVE,
        )
    )
    if has_active_order is True:
        queryset = queryset.filter(active_exists)
    elif has_active_order is False:
        queryset = queryset.filter(~active_exists)

    meal_public_id = (params.get('meal_public_id') or params.get('package_id') or '').strip()
    if meal_public_id:
        queryset = queryset.filter(
            meal_orders__order_status=Order.OrderStatus.ACTIVE,
            meal_orders__meal__public_id=meal_public_id,
        ).distinct()

    registered_from = _parse_date_param(params.get('registered_from'), 'registered_from')
    registered_to = _parse_date_param(params.get('registered_to'), 'registered_to')
    if registered_from is not None:
        queryset = queryset.filter(user__date_joined__date__gte=registered_from)
    if registered_to is not None:
        queryset = queryset.filter(user__date_joined__date__lte=registered_to)

    sort_key = (params.get('sort') or '-date_joined').strip()
    order_by = SORT_ALLOWLIST.get(sort_key)
    if order_by is None:
        raise ValidationError(
            {
                'sort': [
                    f'Unsupported sort. Allowed: {", ".join(sorted(SORT_ALLOWLIST))}.'
                ]
            }
        )
    return queryset.order_by(*order_by)


def _parse_date_param(raw: str | None, field: str) -> date | None:
    if raw is None or raw == '':
        return None
    parsed = parse_date(raw.strip())
    if parsed is None:
        raise ValidationError({field: ['Invalid date. Use YYYY-MM-DD.']})
    return parsed


def get_active_order(customer: CustomerProfile) -> Order | None:
    prefetched = getattr(customer, '_prefetched_active_orders', None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return (
        Order.objects.filter(customer=customer, order_status=Order.OrderStatus.ACTIVE)
        .select_related('meal')
        .order_by('-created_at', '-id')
        .first()
    )


def remaining_meal_count(order: Order | None) -> int:
    if order is None:
        return 0
    return order.deliveries.filter(status=OrderDelivery.DeliveryStatus.SCHEDULED).count()


def build_active_order_payload(customer: CustomerProfile) -> dict[str, Any] | None:
    order = get_active_order(customer)
    if order is None:
        return None
    return {
        'order_public_id': str(order.public_id),
        'package_name': order.meal_name_snapshot,
        'meal_public_id': str(order.meal.public_id) if order.meal_id else None,
        'order_status': order.order_status,
        'order_start_date': order.order_start_date,
        'order_end_date': order.order_end_date,
        'order_month': order.order_month,
        'remaining_meals': remaining_meal_count(order),
        'customer_name': _display_name(customer),
    }


def get_customer_wallet(customer: CustomerProfile) -> Wallet | None:
    try:
        return customer.wallet
    except Wallet.DoesNotExist:
        return None


def build_overview_metrics(customer: CustomerProfile) -> dict[str, Any]:
    orders_qs = Order.objects.filter(customer=customer)
    deliveries_qs = OrderDelivery.objects.filter(order__customer=customer)

    total_orders = orders_qs.count()
    total_meals_delivered = deliveries_qs.filter(
        status=OrderDelivery.DeliveryStatus.DELIVERED
    ).count()
    total_meal_offs = deliveries_qs.filter(
        status=OrderDelivery.DeliveryStatus.SKIPPED
    ).count()

    last_order = orders_qs.order_by('-created_at', '-id').first()
    last_order_at = last_order.created_at if last_order else None

    wallet = get_customer_wallet(customer)
    wallet_balance = wallet.balance if wallet is not None else None
    total_wallet_spent = Decimal('0.00')
    if wallet is not None:
        spent = (
            WalletTransaction.objects.filter(
                wallet=wallet,
                type=WalletTransaction.Type.PAYMENT,
                direction=WalletTransaction.Direction.DEBIT,
                status=WalletTransaction.Status.COMPLETED,
            ).aggregate(total=Sum('amount'))['total']
            or Decimal('0.00')
        )
        total_wallet_spent = spent

    last_activity_at = _resolve_last_activity_at(customer, last_order_at, wallet)

    return {
        'total_orders': total_orders,
        'total_meals_delivered': total_meals_delivered,
        'total_meal_offs': total_meal_offs,
        'total_wallet_spent': f'{total_wallet_spent.quantize(Decimal("0.01")):.2f}',
        'wallet_balance': (
            f'{wallet_balance.quantize(Decimal("0.01")):.2f}'
            if wallet_balance is not None
            else None
        ),
        'wallet_currency': wallet.currency if wallet is not None else None,
        'last_order_at': last_order_at,
        'last_activity_at': last_activity_at,
        'profile_picture_url': None,
    }


def _resolve_last_activity_at(
    customer: CustomerProfile,
    last_order_at: datetime | None,
    wallet: Wallet | None,
) -> datetime | None:
    candidates: list[datetime] = []
    if last_order_at is not None:
        candidates.append(last_order_at)
    if customer.updated_at is not None:
        candidates.append(customer.updated_at)

    last_skip = (
        OrderDelivery.objects.filter(
            order__customer=customer,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
        )
        .order_by('-updated_at', '-id')
        .values_list('updated_at', flat=True)
        .first()
    )
    if last_skip is not None:
        candidates.append(last_skip)

    if wallet is not None:
        last_txn = (
            WalletTransaction.objects.filter(wallet=wallet)
            .order_by('-created_at', '-id')
            .values_list('created_at', flat=True)
            .first()
        )
        if last_txn is not None:
            candidates.append(last_txn)

    return max(candidates) if candidates else None


def _display_name(customer: CustomerProfile) -> str:
    user = customer.user
    full = f'{user.first_name} {user.last_name}'.strip()
    return full or user.email


def customer_orders_queryset(customer: CustomerProfile) -> QuerySet[Order]:
    return (
        Order.objects.filter(customer=customer)
        .select_related('meal')
        .annotate(
            delivered_count=Count(
                'deliveries',
                filter=Q(deliveries__status=OrderDelivery.DeliveryStatus.DELIVERED),
            ),
            skipped_count=Count(
                'deliveries',
                filter=Q(deliveries__status=OrderDelivery.DeliveryStatus.SKIPPED),
            ),
            scheduled_count=Count(
                'deliveries',
                filter=Q(deliveries__status=OrderDelivery.DeliveryStatus.SCHEDULED),
            ),
        )
        .order_by('-created_at', '-id')
    )


def customer_deliveries_queryset(
    customer: CustomerProfile,
    params=None,
    *,
    meal_offs_only: bool = False,
    param_allowlist: frozenset[str] | None = None,
) -> QuerySet[OrderDelivery]:
    qs = (
        OrderDelivery.objects.filter(order__customer=customer)
        .select_related('order', 'order__meal')
        .order_by('-service_date', '-meal_period', '-id')
    )
    if meal_offs_only:
        qs = qs.filter(status=OrderDelivery.DeliveryStatus.SKIPPED)

    if params is None:
        return qs

    allowlist = param_allowlist if param_allowlist is not None else MEAL_QUERY_ALLOWLIST
    reject_unknown_query_params(params, allowlist)

    if 'status' in allowlist:
        status_value = (params.get('status') or '').strip()
        if status_value:
            allowed = {c.value for c in OrderDelivery.DeliveryStatus}
            if status_value not in allowed:
                raise ValidationError(
                    {
                        'status': [
                            f'Invalid status. Allowed: {", ".join(sorted(allowed))}.'
                        ]
                    }
                )
            qs = qs.filter(status=status_value)

    period = (params.get('meal_period') or '').strip()
    if period:
        allowed_periods = {c.value for c in OrderDelivery.MealPeriod}
        if period not in allowed_periods:
            raise ValidationError(
                {
                    'meal_period': [
                        f'Invalid meal_period. Allowed: {", ".join(sorted(allowed_periods))}.'
                    ]
                }
            )
        qs = qs.filter(meal_period=period)

    date_from = _parse_date_param(params.get('service_date_from'), 'service_date_from')
    date_to = _parse_date_param(params.get('service_date_to'), 'service_date_to')
    if date_from is not None:
        qs = qs.filter(service_date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(service_date__lte=date_to)

    return qs


def customer_wallet_transactions_queryset(
    customer: CustomerProfile,
) -> QuerySet[WalletTransaction]:
    wallet = get_customer_wallet(customer)
    if wallet is None:
        return WalletTransaction.objects.none()
    return wallet.transactions.order_by('-created_at', '-id')


def build_activity_events(customer: CustomerProfile, *, limit: int = 200) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for order in Order.objects.filter(customer=customer).order_by('-created_at')[:limit]:
        events.append(
            {
                'event_type': 'order_created',
                'occurred_at': order.created_at,
                'summary': f'Order placed: {order.meal_name_snapshot} ({order.order_month})',
                'refs': {
                    'order_public_id': str(order.public_id),
                    'order_status': order.order_status,
                },
            }
        )

    for hist in (
        OrderStatusHistory.objects.filter(order__customer=customer)
        .select_related('order')
        .order_by('-created_at')[:limit]
    ):
        events.append(
            {
                'event_type': 'order_status_changed',
                'occurred_at': hist.created_at,
                'summary': f'Order status {hist.from_status} → {hist.to_status}',
                'refs': {
                    'order_public_id': str(hist.order.public_id),
                    'from_status': hist.from_status,
                    'to_status': hist.to_status,
                },
            }
        )

    for delivery in (
        OrderDelivery.objects.filter(
            order__customer=customer,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
        )
        .select_related('order')
        .order_by('-updated_at')[:limit]
    ):
        events.append(
            {
                'event_type': 'meal_off',
                'occurred_at': delivery.updated_at or delivery.created_at,
                'summary': (
                    f'Meal off {delivery.meal_period} on {delivery.service_date}'
                    + (f' ({delivery.note})' if delivery.note else '')
                ),
                'refs': {
                    'delivery_public_id': str(delivery.public_id),
                    'order_public_id': str(delivery.order.public_id),
                    'service_date': str(delivery.service_date),
                    'meal_period': delivery.meal_period,
                    'skip_source': delivery.skip_source,
                },
            }
        )

    wallet = get_customer_wallet(customer)
    if wallet is not None:
        for txn in wallet.transactions.order_by('-created_at')[:limit]:
            events.append(
                {
                    'event_type': f'wallet_{txn.type}',
                    'occurred_at': txn.created_at,
                    'summary': (
                        f'Wallet {txn.type} {txn.direction} '
                        f'{txn.amount} ({txn.status})'
                    ),
                    'refs': {
                        'transaction_public_id': str(txn.public_id),
                        'type': txn.type,
                        'direction': txn.direction,
                        'amount': f'{txn.amount:.2f}',
                        'status': txn.status,
                    },
                }
            )

    events.sort(key=lambda item: item['occurred_at'], reverse=True)
    return events[:limit]
