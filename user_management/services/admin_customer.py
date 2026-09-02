"""Admin customer directory and history read helpers (no Request objects)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Exists, OuterRef, Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from orders.models import CustomerSubscription, Order, OrderDelivery, OrderStatusHistory
from orders.services.subscription_service import get_active_subscription
from user_management.models import CustomerAddress, CustomerProfile
from user_management.services.profile_picture import get_profile_picture_url
from user_management.validators import normalize_phone_search_term
from wallet.models import Wallet, WalletTransaction

SUBSCRIPTION_EXPIRING_SOON_DAYS = 14

LIST_QUERY_ALLOWLIST = frozenset(
    {
        'q',
        'is_active',
        'is_email_verified',
        'has_active_order',
        'has_active_subscription',
        'has_wallet',
        'has_pending_recharge',
        'subscription_expiring_soon',
        'inactive_subscription',
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

CONFIRMED_ACTIVITY_EVENT_TYPES = frozenset(
    {
        'subscription_created',
        'subscription_cancelled',
        'wallet_transaction_completed',
        'meal_delivered',
        'meal_skipped',
        'order_created',
        'order_status_changed',
    }
)


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


def customer_delivery_scope(customer: CustomerProfile) -> Q:
    return Q(order__customer=customer) | Q(subscription__customer=customer)


def customer_base_queryset() -> QuerySet[CustomerProfile]:
    return CustomerProfile.objects.select_related('user', 'wallet').prefetch_related(
        Prefetch(
            'addresses',
            queryset=CustomerAddress.objects.order_by('address_type', 'id'),
        ),
        Prefetch(
            'meal_subscriptions',
            queryset=CustomerSubscription.objects.filter(
                status=CustomerSubscription.Status.ACTIVE
            )
            .select_related('meal')
            .order_by('-created_at', '-id'),
            to_attr='_prefetched_active_subscriptions',
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
        phone_q = normalize_phone_search_term(q)
        queryset = queryset.filter(
            Q(user__email__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(phone__icontains=phone_q)
        )

    is_active = parse_bool_param(params.get('is_active'), field='is_active')
    if is_active is not None:
        queryset = queryset.filter(user__is_active=is_active)

    is_email_verified = parse_bool_param(
        params.get('is_email_verified'), field='is_email_verified'
    )
    if is_email_verified is not None:
        queryset = queryset.filter(is_email_verified=is_email_verified)

    active_subscription_exists = Exists(
        CustomerSubscription.objects.filter(
            customer_id=OuterRef('pk'),
            status=CustomerSubscription.Status.ACTIVE,
        )
    )
    has_active_subscription = parse_bool_param(
        params.get('has_active_subscription'), field='has_active_subscription'
    )
    if has_active_subscription is True:
        queryset = queryset.filter(active_subscription_exists)
    elif has_active_subscription is False:
        queryset = queryset.filter(~active_subscription_exists)

    has_active_order = parse_bool_param(
        params.get('has_active_order'), field='has_active_order'
    )
    active_order_exists = Exists(
        Order.objects.filter(
            customer_id=OuterRef('pk'),
            order_status=Order.OrderStatus.ACTIVE,
        )
    )
    if has_active_order is True:
        queryset = queryset.filter(active_order_exists)
    elif has_active_order is False:
        queryset = queryset.filter(~active_order_exists)

    has_wallet = parse_bool_param(params.get('has_wallet'), field='has_wallet')
    wallet_exists = Exists(Wallet.objects.filter(customer_id=OuterRef('pk')))
    if has_wallet is True:
        queryset = queryset.filter(wallet_exists)
    elif has_wallet is False:
        queryset = queryset.filter(~wallet_exists)

    has_pending_recharge = parse_bool_param(
        params.get('has_pending_recharge'), field='has_pending_recharge'
    )
    pending_recharge_exists = Exists(
        WalletTransaction.objects.filter(
            wallet__customer_id=OuterRef('pk'),
            type=WalletTransaction.Type.RECHARGE,
            status=WalletTransaction.Status.PENDING,
        )
    )
    if has_pending_recharge is True:
        queryset = queryset.filter(pending_recharge_exists)
    elif has_pending_recharge is False:
        queryset = queryset.filter(~pending_recharge_exists)

    subscription_expiring_soon = parse_bool_param(
        params.get('subscription_expiring_soon'), field='subscription_expiring_soon'
    )
    if subscription_expiring_soon is not None:
        today = date.today()
        soon_end = today + timedelta(days=SUBSCRIPTION_EXPIRING_SOON_DAYS)
        expiring_exists = Exists(
            CustomerSubscription.objects.filter(
                customer_id=OuterRef('pk'),
                status=CustomerSubscription.Status.ACTIVE,
                cancel_effective_on__isnull=False,
                cancel_effective_on__gte=today,
                cancel_effective_on__lte=soon_end,
            )
        )
        if subscription_expiring_soon:
            queryset = queryset.filter(expiring_exists)
        else:
            queryset = queryset.filter(~expiring_exists)

    inactive_subscription = parse_bool_param(
        params.get('inactive_subscription'), field='inactive_subscription'
    )
    if inactive_subscription is not None:
        any_subscription = Exists(
            CustomerSubscription.objects.filter(customer_id=OuterRef('pk'))
        )
        if inactive_subscription:
            queryset = queryset.filter(any_subscription).filter(~active_subscription_exists)
        else:
            queryset = queryset.filter(~any_subscription | active_subscription_exists)

    meal_public_id = (params.get('meal_public_id') or params.get('package_id') or '').strip()
    if meal_public_id:
        queryset = queryset.filter(
            Q(
                meal_subscriptions__status=CustomerSubscription.Status.ACTIVE,
                meal_subscriptions__meal__public_id=meal_public_id,
            )
            | Q(
                meal_orders__order_status=Order.OrderStatus.ACTIVE,
                meal_orders__meal__public_id=meal_public_id,
            )
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


def get_active_subscription_for_customer(
    customer: CustomerProfile,
) -> CustomerSubscription | None:
    prefetched = getattr(customer, '_prefetched_active_subscriptions', None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return get_active_subscription(customer)


def remaining_meal_count_for_order(order: Order | None) -> int:
    if order is None:
        return 0
    return order.deliveries.filter(status=OrderDelivery.DeliveryStatus.SCHEDULED).count()


def remaining_meal_count_for_subscription(subscription: CustomerSubscription | None) -> int:
    if subscription is None:
        return 0
    return subscription.deliveries.filter(
        status=OrderDelivery.DeliveryStatus.SCHEDULED
    ).count()


def _subscription_delivery_counts(subscription: CustomerSubscription) -> dict[str, int]:
    aggregates = subscription.deliveries.aggregate(
        delivered_count=Count(
            'id',
            filter=Q(status=OrderDelivery.DeliveryStatus.DELIVERED),
        ),
        skipped_count=Count(
            'id',
            filter=Q(status=OrderDelivery.DeliveryStatus.SKIPPED),
        ),
        scheduled_count=Count(
            'id',
            filter=Q(status=OrderDelivery.DeliveryStatus.SCHEDULED),
        ),
    )
    return {
        'delivered_count': aggregates['delivered_count'] or 0,
        'skipped_count': aggregates['skipped_count'] or 0,
        'remaining_meals': aggregates['scheduled_count'] or 0,
    }


def build_active_subscription_payload(
    customer: CustomerProfile,
) -> dict[str, Any] | None:
    subscription = get_active_subscription_for_customer(customer)
    if subscription is None:
        return None
    counts = _subscription_delivery_counts(subscription)
    return {
        'subscription_public_id': str(subscription.public_id),
        'package_name': subscription.meal_name_snapshot,
        'meal_public_id': str(subscription.meal.public_id) if subscription.meal_id else None,
        'status': subscription.status,
        'started_on': subscription.started_on,
        'cancel_effective_on': subscription.cancel_effective_on,
        'cancelled_at': subscription.cancelled_at,
        'remaining_meals': counts['remaining_meals'],
        'delivered_count': counts['delivered_count'],
        'skipped_count': counts['skipped_count'],
        'customer_name': _display_name(customer),
    }


def build_current_package_summary(customer: CustomerProfile) -> dict[str, Any] | None:
    subscription = get_active_subscription_for_customer(customer)
    if subscription is not None:
        counts = _subscription_delivery_counts(subscription)
        return {
            'subscription_public_id': str(subscription.public_id),
            'package_name': subscription.meal_name_snapshot,
            'meal_public_id': str(subscription.meal.public_id) if subscription.meal_id else None,
            'status': subscription.status,
            'started_on': subscription.started_on,
            'cancel_effective_on': subscription.cancel_effective_on,
            'remaining_meals': counts['remaining_meals'],
        }
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
        'remaining_meals': remaining_meal_count_for_order(order),
    }


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
        'remaining_meals': remaining_meal_count_for_order(order),
        'customer_name': _display_name(customer),
    }


def get_customer_wallet(customer: CustomerProfile) -> Wallet | None:
    try:
        return customer.wallet
    except Wallet.DoesNotExist:
        return None


def customer_has_legacy_orders(customer: CustomerProfile) -> bool:
    return Order.objects.filter(customer=customer).exists()


def _wallet_aggregate(
    wallet: Wallet,
    *,
    txn_type: str,
    direction: str | None = None,
    txn_status: str | None = None,
) -> Decimal:
    qs = WalletTransaction.objects.filter(wallet=wallet, type=txn_type)
    if direction is not None:
        qs = qs.filter(direction=direction)
    if txn_status is not None:
        qs = qs.filter(status=txn_status)
    total = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return total


def build_wallet_overview(customer: CustomerProfile) -> dict[str, Any]:
    wallet = get_customer_wallet(customer)
    if wallet is None:
        return {
            'available_balance': None,
            'pending_recharge_amount': '0.00',
            'pending_withdraw_amount': '0.00',
            'total_recharged': '0.00',
            'total_withdrawn': '0.00',
            'total_spent': '0.00',
            'wallet_status': None,
            'wallet_currency': None,
            'pending_funding_request_count': 0,
        }

    pending_recharge = _wallet_aggregate(
        wallet,
        txn_type=WalletTransaction.Type.RECHARGE,
        txn_status=WalletTransaction.Status.PENDING,
    )
    pending_withdraw = _wallet_aggregate(
        wallet,
        txn_type=WalletTransaction.Type.WITHDRAW,
        txn_status=WalletTransaction.Status.PENDING,
    )
    total_recharged = _wallet_aggregate(
        wallet,
        txn_type=WalletTransaction.Type.RECHARGE,
        direction=WalletTransaction.Direction.CREDIT,
        txn_status=WalletTransaction.Status.COMPLETED,
    )
    total_withdrawn = _wallet_aggregate(
        wallet,
        txn_type=WalletTransaction.Type.WITHDRAW,
        direction=WalletTransaction.Direction.DEBIT,
        txn_status=WalletTransaction.Status.COMPLETED,
    )
    total_spent = _wallet_aggregate(
        wallet,
        txn_type=WalletTransaction.Type.PAYMENT,
        direction=WalletTransaction.Direction.DEBIT,
        txn_status=WalletTransaction.Status.COMPLETED,
    )
    pending_count = wallet.transactions.filter(status=WalletTransaction.Status.PENDING).count()

    return {
        'available_balance': f'{wallet.balance.quantize(Decimal("0.01")):.2f}',
        'pending_recharge_amount': f'{pending_recharge.quantize(Decimal("0.01")):.2f}',
        'pending_withdraw_amount': f'{pending_withdraw.quantize(Decimal("0.01")):.2f}',
        'total_recharged': f'{total_recharged.quantize(Decimal("0.01")):.2f}',
        'total_withdrawn': f'{total_withdrawn.quantize(Decimal("0.01")):.2f}',
        'total_spent': f'{total_spent.quantize(Decimal("0.01")):.2f}',
        'wallet_status': wallet.status,
        'wallet_currency': wallet.currency,
        'pending_funding_request_count': pending_count,
    }


def build_wallet_summary(customer: CustomerProfile) -> dict[str, Any]:
    return build_wallet_overview(customer)


def build_overview_metrics(customer: CustomerProfile) -> dict[str, Any]:
    scope = customer_delivery_scope(customer)
    deliveries_qs = OrderDelivery.objects.filter(scope)

    total_subscriptions = CustomerSubscription.objects.filter(customer=customer).count()
    total_orders = Order.objects.filter(customer=customer).count()
    total_meals_delivered = deliveries_qs.filter(
        status=OrderDelivery.DeliveryStatus.DELIVERED
    ).count()
    total_meal_offs = deliveries_qs.filter(
        status=OrderDelivery.DeliveryStatus.SKIPPED
    ).count()

    last_subscription = (
        CustomerSubscription.objects.filter(customer=customer)
        .order_by('-created_at', '-id')
        .first()
    )
    last_subscription_at = last_subscription.created_at if last_subscription else None

    last_order = Order.objects.filter(customer=customer).order_by('-created_at', '-id').first()
    last_order_at = last_order.created_at if last_order else None

    last_meal_delivered = (
        deliveries_qs.filter(status=OrderDelivery.DeliveryStatus.DELIVERED)
        .order_by('-marked_at', '-service_date', '-id')
        .values_list('marked_at', 'service_date')
        .first()
    )
    last_meal_delivered_at = None
    if last_meal_delivered is not None:
        marked_at, service_date = last_meal_delivered
        if marked_at is not None:
            last_meal_delivered_at = marked_at
        elif service_date is not None:
            last_meal_delivered_at = timezone.make_aware(
                datetime.combine(service_date, datetime.min.time())
            )

    wallet = get_customer_wallet(customer)
    wallet_balance = wallet.balance if wallet is not None else None
    total_wallet_spent = Decimal('0.00')
    total_wallet_recharged = Decimal('0.00')
    total_wallet_withdrawn = Decimal('0.00')
    last_payment_at = None
    if wallet is not None:
        total_wallet_spent = _wallet_aggregate(
            wallet,
            txn_type=WalletTransaction.Type.PAYMENT,
            direction=WalletTransaction.Direction.DEBIT,
            txn_status=WalletTransaction.Status.COMPLETED,
        )
        total_wallet_recharged = _wallet_aggregate(
            wallet,
            txn_type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            txn_status=WalletTransaction.Status.COMPLETED,
        )
        total_wallet_withdrawn = _wallet_aggregate(
            wallet,
            txn_type=WalletTransaction.Type.WITHDRAW,
            direction=WalletTransaction.Direction.DEBIT,
            txn_status=WalletTransaction.Status.COMPLETED,
        )
        last_payment = (
            wallet.transactions.filter(
                type=WalletTransaction.Type.PAYMENT,
                direction=WalletTransaction.Direction.DEBIT,
                status=WalletTransaction.Status.COMPLETED,
            )
            .order_by('-created_at', '-id')
            .values_list('created_at', flat=True)
            .first()
        )
        last_payment_at = last_payment

    active_subscription = get_active_subscription_for_customer(customer)
    current_package_expires_at = None
    if active_subscription is not None and active_subscription.cancel_effective_on:
        current_package_expires_at = active_subscription.cancel_effective_on
    elif get_active_order(customer) is not None:
        current_package_expires_at = get_active_order(customer).order_end_date

    last_activity_at = _resolve_last_activity_at(
        customer,
        last_order_at=last_order_at,
        last_subscription_at=last_subscription_at,
        wallet=wallet,
        scope=scope,
    )

    return {
        'total_subscriptions': total_subscriptions,
        'total_orders': total_orders,
        'total_meals_delivered': total_meals_delivered,
        'total_meal_offs': total_meal_offs,
        'customer_lifetime_value': f'{total_wallet_spent.quantize(Decimal("0.01")):.2f}',
        'total_wallet_spent': f'{total_wallet_spent.quantize(Decimal("0.01")):.2f}',
        'total_wallet_recharged': f'{total_wallet_recharged.quantize(Decimal("0.01")):.2f}',
        'total_wallet_withdrawn': f'{total_wallet_withdrawn.quantize(Decimal("0.01")):.2f}',
        'wallet_balance': (
            f'{wallet_balance.quantize(Decimal("0.01")):.2f}'
            if wallet_balance is not None
            else None
        ),
        'wallet_currency': wallet.currency if wallet is not None else None,
        'last_payment_at': last_payment_at,
        'last_meal_delivered_at': last_meal_delivered_at,
        'current_package_expires_at': current_package_expires_at,
        'last_subscription_at': last_subscription_at,
        'last_order_at': last_order_at,
        'last_activity_at': last_activity_at,
        'has_legacy_orders': customer_has_legacy_orders(customer),
        'profile_picture_url': get_profile_picture_url(customer),
    }


def _resolve_last_activity_at(
    customer: CustomerProfile,
    *,
    last_order_at: datetime | None,
    last_subscription_at: datetime | None,
    wallet: Wallet | None,
    scope: Q,
) -> datetime | None:
    candidates: list[datetime] = []
    if last_order_at is not None:
        candidates.append(last_order_at)
    if last_subscription_at is not None:
        candidates.append(last_subscription_at)
    if customer.updated_at is not None:
        candidates.append(customer.updated_at)

    last_delivered = (
        OrderDelivery.objects.filter(scope, status=OrderDelivery.DeliveryStatus.DELIVERED)
        .order_by('-marked_at', '-updated_at', '-id')
        .values_list('marked_at', 'updated_at')
        .first()
    )
    if last_delivered is not None:
        marked_at, updated_at = last_delivered
        candidates.append(marked_at or updated_at)

    last_skip = (
        OrderDelivery.objects.filter(scope, status=OrderDelivery.DeliveryStatus.SKIPPED)
        .order_by('-updated_at', '-id')
        .values_list('updated_at', flat=True)
        .first()
    )
    if last_skip is not None:
        candidates.append(last_skip)

    if wallet is not None:
        last_txn = (
            WalletTransaction.objects.filter(
                wallet=wallet,
                status=WalletTransaction.Status.COMPLETED,
            )
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


def customer_subscriptions_queryset(customer: CustomerProfile) -> QuerySet[CustomerSubscription]:
    return (
        CustomerSubscription.objects.filter(customer=customer)
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
        OrderDelivery.objects.filter(customer_delivery_scope(customer))
        .select_related('order', 'order__meal', 'subscription', 'subscription__meal')
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
    scope = customer_delivery_scope(customer)

    for subscription in (
        CustomerSubscription.objects.filter(customer=customer).order_by('-created_at')[:limit]
    ):
        events.append(
            {
                'event_type': 'subscription_created',
                'occurred_at': subscription.created_at,
                'summary': f'Subscribed: {subscription.meal_name_snapshot}',
                'refs': {
                    'subscription_public_id': str(subscription.public_id),
                    'status': subscription.status,
                },
            }
        )
        if subscription.cancelled_at is not None:
            events.append(
                {
                    'event_type': 'subscription_cancelled',
                    'occurred_at': subscription.cancelled_at,
                    'summary': f'Subscription cancelled: {subscription.meal_name_snapshot}',
                    'refs': {
                        'subscription_public_id': str(subscription.public_id),
                        'cancel_effective_on': (
                            str(subscription.cancel_effective_on)
                            if subscription.cancel_effective_on
                            else None
                        ),
                    },
                }
            )

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
        OrderDelivery.objects.filter(scope, status=OrderDelivery.DeliveryStatus.DELIVERED)
        .select_related('order', 'subscription')
        .order_by('-marked_at', '-service_date')[:limit]
    ):
        occurred_at = delivery.marked_at or delivery.updated_at or delivery.created_at
        package_name = _delivery_package_name(delivery)
        events.append(
            {
                'event_type': 'meal_delivered',
                'occurred_at': occurred_at,
                'summary': f'Meal delivered {delivery.meal_period} on {delivery.service_date} ({package_name})',
                'refs': {
                    'delivery_public_id': str(delivery.public_id),
                    'service_date': str(delivery.service_date),
                    'meal_period': delivery.meal_period,
                },
            }
        )

    for delivery in (
        OrderDelivery.objects.filter(scope, status=OrderDelivery.DeliveryStatus.SKIPPED)
        .select_related('order', 'subscription')
        .order_by('-updated_at', '-service_date')[:limit]
    ):
        occurred_at = delivery.updated_at or delivery.created_at
        package_name = _delivery_package_name(delivery)
        events.append(
            {
                'event_type': 'meal_skipped',
                'occurred_at': occurred_at,
                'summary': (
                    f'Meal skipped {delivery.meal_period} on {delivery.service_date} ({package_name})'
                    + (f' — {delivery.note}' if delivery.note else '')
                ),
                'refs': {
                    'delivery_public_id': str(delivery.public_id),
                    'service_date': str(delivery.service_date),
                    'meal_period': delivery.meal_period,
                    'skip_source': delivery.skip_source,
                },
            }
        )

    wallet = get_customer_wallet(customer)
    if wallet is not None:
        for txn in wallet.transactions.filter(
            status=WalletTransaction.Status.COMPLETED
        ).order_by('-created_at')[:limit]:
            events.append(
                {
                    'event_type': 'wallet_transaction_completed',
                    'occurred_at': txn.created_at,
                    'summary': (
                        f'Wallet {txn.type} {txn.direction} '
                        f'{txn.amount} completed'
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

    events = [e for e in events if e['event_type'] in CONFIRMED_ACTIVITY_EVENT_TYPES]
    events.sort(key=lambda item: item['occurred_at'], reverse=True)
    return events[:limit]


def _delivery_package_name(delivery: OrderDelivery) -> str:
    if delivery.order_id:
        return delivery.order.meal_name_snapshot
    if delivery.subscription_id:
        return delivery.subscription.meal_name_snapshot
    return 'Unknown package'


# Backward-compatible alias used by serializers during migration.
remaining_meal_count = remaining_meal_count_for_order
