"""Guest meal prepaid orders for active subscribers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Sum

from meals.services.pricing import periods_for_meal_period
from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import GuestMealOrder, OrderDelivery, OrderWalletSettings
from orders.services.meal_off import (
    get_meal_off_settings,
    is_past_meal_cutoff,
    meal_off_business_now,
)
from orders.services.order_wallet_settings import get_order_wallet_settings
from orders.services.subscription_service import (
    business_today,
    ensure_subscription_deliveries,
    get_active_subscription,
)
from wallet.models import Wallet, WalletTransaction
from wallet.services.ledger import (
    InsufficientFundsError,
    WalletFrozenError,
    debit_wallet,
    get_or_create_wallet,
)

MONEY = Decimal('0.01')
GUEST_MEAL_PURPOSE = 'guest_meal'
MAX_PER_REQUEST_QUANTITY = 10
PERSONAL_MEAL_OFF_MESSAGE = (
    'Guest Meal cannot be ordered because your regular meal is OFF for this date.'
)
COUNTABLE_STATUSES = (
    GuestMealOrder.Status.SCHEDULED,
    GuestMealOrder.Status.DELIVERED,
)
COOKING_STATUSES = (
    GuestMealOrder.Status.SCHEDULED,
    GuestMealOrder.Status.DELIVERED,
)


class GuestMealError(Exception):
    def __init__(self, message: str, *, code: str = 'GUEST_MEAL_ERROR'):
        super().__init__(message)
        self.code = code


class GuestMealNotEligibleError(GuestMealError):
    pass


class GuestMealValidationError(GuestMealError):
    pass


class GuestMealQuotaError(GuestMealError):
    pass


class GuestMealWalletError(GuestMealError):
    pass


@dataclass(frozen=True)
class GuestMealQuote:
    service_date: date
    meal_period: str
    quantity: int
    base_meal_price: Decimal
    box_price: Decimal
    unit_price: Decimal
    total_amount: Decimal
    monthly_limit: int
    monthly_used: int
    monthly_remaining: int
    monthly_remaining_after_order: int
    recharge_balance: Decimal
    meal_stop_threshold: Decimal
    recharge_balance_after: Decimal
    cutoff_passed: bool
    subscription_public_id: str


def _quantize(amount: Decimal) -> Decimal:
    return Decimal(amount).quantize(MONEY)


def normalize_guest_quantity(value) -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError) as exc:
        raise GuestMealValidationError(
            'quantity must be a positive integer.',
            code='INVALID_QUANTITY',
        ) from exc
    if qty < 1:
        raise GuestMealValidationError(
            'quantity must be a positive integer.',
            code='INVALID_QUANTITY',
        )
    if qty > MAX_PER_REQUEST_QUANTITY:
        raise GuestMealValidationError(
            f'quantity must not exceed {MAX_PER_REQUEST_QUANTITY} per request.',
            code='INVALID_QUANTITY',
        )
    return qty


def parse_guest_meal_period(raw: str) -> str:
    if raw not in (
        GuestMealOrder.MealPeriod.LUNCH,
        GuestMealOrder.MealPeriod.DINNER,
    ):
        raise GuestMealValidationError(
            'meal_period must be lunch or dinner.',
            code='INVALID_MEAL_PERIOD',
        )
    return raw


def business_now() -> datetime:
    return meal_off_business_now(get_meal_off_settings())


def calendar_month_bounds(reference: date | None = None) -> tuple[datetime, datetime]:
    """Inclusive start / exclusive end of Asia/Dhaka calendar month as aware datetimes."""
    settings_obj = get_meal_off_settings()
    tz = ZoneInfo(settings_obj.timezone)
    ref = reference or business_today()
    start = datetime(ref.year, ref.month, 1, 0, 0, 0, tzinfo=tz)
    if ref.month == 12:
        end = datetime(ref.year + 1, 1, 1, 0, 0, 0, tzinfo=tz)
    else:
        end = datetime(ref.year, ref.month + 1, 1, 0, 0, 0, tzinfo=tz)
    return start, end


def monthly_used_quantity(
    customer,
    *,
    reference: date | None = None,
    exclude_pk: int | None = None,
) -> int:
    start, end = calendar_month_bounds(reference)
    qs = GuestMealOrder.objects.filter(
        customer=customer,
        status__in=COUNTABLE_STATUSES,
        created_at__gte=start,
        created_at__lt=end,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    total = qs.aggregate(total=Sum('quantity'))['total']
    return int(total or 0)


def guest_usage_summary(customer, *, reference: date | None = None) -> dict:
    settings_obj = get_order_wallet_settings()
    limit = int(settings_obj.guest_meal_monthly_limit)
    used = monthly_used_quantity(customer, reference=reference)
    remaining = max(limit - used, 0)
    ref = reference or business_today()
    return {
        'calendar_month': f'{ref.year:04d}-{ref.month:02d}',
        'monthly_limit': limit,
        'used_quantity': used,
        'remaining_quantity': remaining,
    }


def guest_quantity_for_delivery(delivery: OrderDelivery) -> int:
    total = (
        GuestMealOrder.objects.filter(
            delivery=delivery,
            status__in=COOKING_STATUSES,
        ).aggregate(total=Sum('quantity'))['total']
    )
    return int(total or 0)


def guest_quantities_by_delivery_ids(delivery_ids: list[int]) -> dict[int, int]:
    if not delivery_ids:
        return {}
    rows = (
        GuestMealOrder.objects.filter(
            delivery_id__in=delivery_ids,
            status__in=COOKING_STATUSES,
        )
        .values('delivery_id')
        .annotate(total=Sum('quantity'))
    )
    return {int(row['delivery_id']): int(row['total'] or 0) for row in rows}


def guest_cooking_quantity_for_slot(
    *,
    service_date: date,
    meal_period: str,
    package_id: int | None = None,
) -> int:
    qs = GuestMealOrder.objects.filter(
        service_date=service_date,
        meal_period=meal_period,
        status__in=COOKING_STATUSES,
    )
    if package_id is not None:
        qs = qs.filter(subscription__meal_id=package_id)
    total = qs.aggregate(total=Sum('quantity'))['total']
    return int(total or 0)


def guest_cooking_quantities_by_package(
    *,
    service_date: date,
    meal_period: str,
) -> dict[int, int]:
    rows = (
        GuestMealOrder.objects.filter(
            service_date=service_date,
            meal_period=meal_period,
            status__in=COOKING_STATUSES,
        )
        .values('subscription__meal_id')
        .annotate(total=Sum('quantity'))
    )
    return {
        int(row['subscription__meal_id']): int(row['total'] or 0)
        for row in rows
        if row['subscription__meal_id'] is not None
    }


def resolve_guest_pricing(
    *,
    meal_id: int,
    service_date: date,
    meal_period: str,
    quantity: int,
    settings_obj: OrderWalletSettings | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    settings_obj = settings_obj or get_order_wallet_settings()
    slot = resolve_published_slot_for_delivery(
        meal_id=meal_id,
        service_date=service_date,
        meal_period=meal_period,
    )
    if slot is None or slot.final_meal_price_snapshot is None:
        raise GuestMealNotEligibleError(
            'Meal price is unavailable for this date and meal period.',
            code='PRICE_UNAVAILABLE',
        )
    base = _quantize(Decimal(slot.final_meal_price_snapshot))
    box = _quantize(Decimal(settings_obj.guest_meal_box_price))
    unit = _quantize(base + box)
    total = _quantize(unit * Decimal(quantity))
    return base, box, unit, total


def is_personal_meal_off(
    customer,
    *,
    service_date: date,
    meal_period: str,
    subscription=None,
) -> bool:
    """
    True when the regular slot is customer-requested Meal-OFF.

    Authoritative shape: OrderDelivery skipped with skip_source=customer.
    Admin/system skips are intentionally excluded.
    """
    qs = OrderDelivery.objects.filter(
        service_date=service_date,
        meal_period=meal_period,
        status=OrderDelivery.DeliveryStatus.SKIPPED,
        skip_source=OrderDelivery.SkipSource.CUSTOMER,
    )
    if subscription is not None:
        qs = qs.filter(subscription_id=subscription.pk)
    else:
        qs = qs.filter(subscription__customer=customer)
    return qs.exists()


def delivery_is_personal_meal_off(delivery: OrderDelivery) -> bool:
    return (
        delivery.status == OrderDelivery.DeliveryStatus.SKIPPED
        and delivery.skip_source == OrderDelivery.SkipSource.CUSTOMER
    )


def has_scheduled_guest_meals_for_slot(
    *,
    customer,
    service_date: date,
    meal_period: str,
) -> bool:
    """True when countable (scheduled) Guest Meals exist for this slot."""
    return GuestMealOrder.objects.filter(
        customer=customer,
        service_date=service_date,
        meal_period=meal_period,
        status=GuestMealOrder.Status.SCHEDULED,
    ).exists()


def _resolve_linked_delivery(subscription, service_date: date, meal_period: str):
    ensure_subscription_deliveries(subscription)
    return (
        OrderDelivery.objects.filter(
            subscription=subscription,
            service_date=service_date,
            meal_period=meal_period,
        )
        .order_by('id')
        .first()
    )


def _lock_delivery_for_guest_create(delivery_pk: int) -> OrderDelivery:
    return (
        OrderDelivery.objects.select_for_update(of=('self',))
        .select_related('subscription')
        .get(pk=delivery_pk)
    )


def build_guest_meal_quote(
    customer,
    *,
    service_date: date,
    meal_period: str,
    quantity,
) -> GuestMealQuote:
    meal_period = parse_guest_meal_period(meal_period)
    quantity = normalize_guest_quantity(quantity)
    subscription = get_active_subscription(customer)
    if subscription is None:
        raise GuestMealNotEligibleError(
            'An active meal subscription is required to order guest meals.',
            code='NO_ACTIVE_SUBSCRIPTION',
        )

    today = business_today()
    if service_date < today:
        raise GuestMealValidationError(
            'Guest meals cannot be ordered for past dates.',
            code='INVALID_DATE',
        )

    allowed_periods = periods_for_meal_period(subscription.meal_period_snapshot)
    if meal_period not in allowed_periods:
        raise GuestMealNotEligibleError(
            'This meal period is not covered by your subscription.',
            code='UNSUPPORTED_MEAL_PERIOD',
        )

    settings_obj = get_order_wallet_settings()
    cutoff_passed = is_past_meal_cutoff(service_date, meal_period)
    if cutoff_passed:
        raise GuestMealNotEligibleError(
            'Ordering cutoff for this meal has already passed.',
            code='CUTOFF_PASSED',
        )

    # Ensure slots exist so personal Meal-OFF is evaluated against real rows.
    ensure_subscription_deliveries(subscription)
    if is_personal_meal_off(
        customer,
        service_date=service_date,
        meal_period=meal_period,
        subscription=subscription,
    ):
        raise GuestMealNotEligibleError(
            PERSONAL_MEAL_OFF_MESSAGE,
            code='PERSONAL_MEAL_OFF',
        )

    base, box, unit, total = resolve_guest_pricing(
        meal_id=subscription.meal_id,
        service_date=service_date,
        meal_period=meal_period,
        quantity=quantity,
        settings_obj=settings_obj,
    )

    usage = guest_usage_summary(customer)
    if quantity > usage['remaining_quantity']:
        raise GuestMealQuotaError(
            'Monthly guest meal limit would be exceeded.',
            code='MONTHLY_LIMIT_EXCEEDED',
        )

    wallet = get_or_create_wallet(customer)
    recharge = _quantize(Decimal(wallet.recharge_balance))
    threshold = _quantize(Decimal(settings_obj.meal_stop_threshold))
    after = _quantize(recharge - total)
    if after < threshold:
        raise GuestMealWalletError(
            'Insufficient recharge balance above meal-stop threshold for this guest meal.',
            code='MEAL_STOP_FLOOR',
        )

    return GuestMealQuote(
        service_date=service_date,
        meal_period=meal_period,
        quantity=quantity,
        base_meal_price=base,
        box_price=box,
        unit_price=unit,
        total_amount=total,
        monthly_limit=usage['monthly_limit'],
        monthly_used=usage['used_quantity'],
        monthly_remaining=usage['remaining_quantity'],
        monthly_remaining_after_order=usage['remaining_quantity'] - quantity,
        recharge_balance=recharge,
        meal_stop_threshold=threshold,
        recharge_balance_after=after,
        cutoff_passed=False,
        subscription_public_id=str(subscription.public_id),
    )


def preview_guest_meal(
    customer,
    *,
    service_date: date,
    meal_period: str,
    quantity,
) -> dict:
    quote = build_guest_meal_quote(
        customer,
        service_date=service_date,
        meal_period=meal_period,
        quantity=quantity,
    )
    return quote_to_dict(quote, include_eligibility=True)


def quote_to_dict(quote: GuestMealQuote, *, include_eligibility: bool = False) -> dict:
    payload = {
        'date': quote.service_date.isoformat(),
        'meal_period': quote.meal_period,
        'quantity': quote.quantity,
        'base_meal_price': f'{quote.base_meal_price:.2f}',
        'box_price': f'{quote.box_price:.2f}',
        'unit_price': f'{quote.unit_price:.2f}',
        'total_price': f'{quote.total_amount:.2f}',
        'monthly_limit': quote.monthly_limit,
        'monthly_used': quote.monthly_used,
        'monthly_remaining': quote.monthly_remaining,
        'monthly_remaining_after_order': quote.monthly_remaining_after_order,
        'recharge_balance': f'{quote.recharge_balance:.2f}',
        'meal_stop_threshold': f'{quote.meal_stop_threshold:.2f}',
        'recharge_balance_after': f'{quote.recharge_balance_after:.2f}',
        'subscription_public_id': quote.subscription_public_id,
        'cutoff_passed': quote.cutoff_passed,
    }
    if include_eligibility:
        payload['eligible'] = True
    return payload


def serialize_guest_meal_order(order: GuestMealOrder) -> dict:
    return {
        'public_id': str(order.public_id),
        'date': order.service_date.isoformat(),
        'meal_period': order.meal_period,
        'quantity': order.quantity,
        'base_meal_price': f'{order.base_meal_price:.2f}',
        'box_price': f'{order.box_price:.2f}',
        'unit_price': f'{order.unit_price:.2f}',
        'total_price': f'{order.total_amount:.2f}',
        'status': order.status,
        'subscription_public_id': str(order.subscription.public_id),
        'delivery_public_id': (
            str(order.delivery.public_id) if order.delivery_id else None
        ),
        'wallet_transaction_public_id': (
            str(order.wallet_transaction.public_id)
            if order.wallet_transaction_id
            else None
        ),
        'created_at': order.created_at.isoformat().replace('+00:00', 'Z'),
    }


def _admin_customer_display_name(customer) -> str:
    if customer is None:
        return ''
    user = getattr(customer, 'user', None)
    if user is not None:
        full = f'{user.first_name} {user.last_name}'.strip()
        if full:
            return full
        email = (user.email or '').strip()
        if email:
            return email
        username = (user.username or '').strip()
        if username:
            return username
    return ''


def serialize_admin_guest_meal_order(order: GuestMealOrder) -> dict:
    """Cross-customer admin list/detail payload (verified admin only)."""
    from user_management.validators import format_bd_phone_e164

    customer = order.customer
    meal = getattr(order.subscription, 'meal', None)
    delivery = order.delivery
    zone = getattr(delivery, 'logistics_zone', None) if delivery is not None else None
    return {
        'public_id': str(order.public_id),
        'customer_public_id': str(customer.public_id),
        'customer_name': _admin_customer_display_name(customer),
        'customer_phone': format_bd_phone_e164(customer.phone) if customer.phone else None,
        'service_date': order.service_date.isoformat(),
        'meal_period': order.meal_period,
        'quantity': order.quantity,
        'package_public_id': str(meal.public_id) if meal is not None else None,
        'package_name': meal.meal_name if meal is not None else '',
        'subscription_public_id': str(order.subscription.public_id),
        'delivery_public_id': (
            str(delivery.public_id) if delivery is not None else None
        ),
        'zone_public_id': str(zone.public_id) if zone is not None else None,
        'zone_name': zone.name if zone is not None else None,
        'base_meal_price': f'{order.base_meal_price:.2f}',
        'box_price': f'{order.box_price:.2f}',
        'unit_price': f'{order.unit_price:.2f}',
        'total_amount': f'{order.total_amount:.2f}',
        'status': order.status,
        'wallet_transaction_public_id': (
            str(order.wallet_transaction.public_id)
            if order.wallet_transaction_id
            else None
        ),
        'created_at': order.created_at.isoformat().replace('+00:00', 'Z'),
    }


def admin_guest_meal_queryset():
    return (
        GuestMealOrder.objects.select_related(
            'customer__user',
            'subscription__meal',
            'delivery__logistics_zone',
            'wallet_transaction',
        )
        .all()
        .order_by('-service_date', '-created_at')
    )


def summarize_admin_guest_meals(qs) -> dict:
    from django.db.models import Count, Q, Sum

    from admin_wallet.models import MealProfitTransaction

    aggregates = qs.aggregate(
        order_count=Count('id'),
        box_quantity=Sum('quantity'),
        revenue=Sum('total_amount'),
        scheduled_box_quantity=Sum(
            'quantity',
            filter=Q(status=GuestMealOrder.Status.SCHEDULED),
        ),
        delivered_box_quantity=Sum(
            'quantity',
            filter=Q(status=GuestMealOrder.Status.DELIVERED),
        ),
        cancelled_box_quantity=Sum(
            'quantity',
            filter=Q(status=GuestMealOrder.Status.CANCELLED),
        ),
        delivered_order_value=Sum(
            'total_amount',
            filter=Q(status=GuestMealOrder.Status.DELIVERED),
        ),
    )
    revenue = aggregates['revenue']
    prepaid = f'{(revenue or 0):.2f}'
    delivered_recognized = f'{(aggregates["delivered_order_value"] or 0):.2f}'

    guest_ids = list(qs.values_list('id', flat=True))
    realized_profit = (
        MealProfitTransaction.objects.filter(
            meal_kind=MealProfitTransaction.MealKind.GUEST,
            guest_meal_order_id__in=guest_ids,
        ).aggregate(total=Sum('profit_amount'))['total']
        if guest_ids
        else None
    )
    return {
        'order_count': int(aggregates['order_count'] or 0),
        'box_quantity': int(aggregates['box_quantity'] or 0),
        # Legacy key: prepaid order value across all statuses in the filter.
        'revenue': prepaid,
        'prepaid_order_value': prepaid,
        'delivered_recognized_revenue': delivered_recognized,
        'realized_guest_profit': f'{(realized_profit or 0):.2f}',
        'scheduled_box_quantity': int(aggregates['scheduled_box_quantity'] or 0),
        'delivered_box_quantity': int(aggregates['delivered_box_quantity'] or 0),
        'cancelled_box_quantity': int(aggregates['cancelled_box_quantity'] or 0),
    }


def _find_idempotent_order(customer, idempotency_key: str | None):
    if not idempotency_key:
        return None
    return (
        GuestMealOrder.objects.filter(
            customer=customer,
            idempotency_key=idempotency_key,
        )
        .select_related('subscription', 'delivery', 'wallet_transaction')
        .first()
    )


def _idempotency_payload_matches(order: GuestMealOrder, *, service_date, meal_period, quantity) -> bool:
    return (
        order.service_date == service_date
        and order.meal_period == meal_period
        and order.quantity == quantity
    )


@transaction.atomic
def create_guest_meal_order(
    customer,
    *,
    service_date: date,
    meal_period: str,
    quantity,
    idempotency_key: str | None = None,
) -> tuple[GuestMealOrder, dict]:
    """
    Atomically validate, debit wallet, and create a GuestMealOrder.

    Returns (order, response_dict including usage after purchase).
    """
    meal_period = parse_guest_meal_period(meal_period)
    quantity = normalize_guest_quantity(quantity)
    key = (idempotency_key or '').strip() or None

    existing = _find_idempotent_order(customer, key)
    if existing is not None:
        if not _idempotency_payload_matches(
            existing,
            service_date=service_date,
            meal_period=meal_period,
            quantity=quantity,
        ):
            raise GuestMealValidationError(
                'Idempotency key was already used with a different guest meal payload.',
                code='IDEMPOTENCY_CONFLICT',
            )
        usage = guest_usage_summary(customer)
        payload = serialize_guest_meal_order(existing)
        payload.update(
            {
                'monthly_limit': usage['monthly_limit'],
                'monthly_used': usage['used_quantity'],
                'monthly_remaining': usage['remaining_quantity'],
                'monthly_remaining_after_order': usage['remaining_quantity'],
                'idempotent_replay': True,
            }
        )
        return existing, payload

    # Lock wallet early to serialize concurrent guest purchases for this customer.
    wallet = get_or_create_wallet(customer)
    locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

    # Lock existing month rows so concurrent quota checks serialize.
    start, end = calendar_month_bounds()
    list(
        GuestMealOrder.objects.select_for_update()
        .filter(
            customer=customer,
            created_at__gte=start,
            created_at__lt=end,
        )
        .order_by('id')
    )

    quote = build_guest_meal_quote(
        customer,
        service_date=service_date,
        meal_period=meal_period,
        quantity=quantity,
    )
    subscription = get_active_subscription(customer)
    if subscription is None:
        raise GuestMealNotEligibleError(
            'An active meal subscription is required to order guest meals.',
            code='NO_ACTIVE_SUBSCRIPTION',
        )

    # Re-check floor against locked wallet recharge balance.
    recharge = _quantize(Decimal(locked_wallet.recharge_balance))
    threshold = quote.meal_stop_threshold
    if _quantize(recharge - quote.total_amount) < threshold:
        raise GuestMealWalletError(
            'Insufficient recharge balance above meal-stop threshold for this guest meal.',
            code='MEAL_STOP_FLOOR',
        )

    delivery = _resolve_linked_delivery(subscription, service_date, meal_period)
    if delivery is None:
        raise GuestMealNotEligibleError(
            'A delivery stop is not available for this date and meal period.',
            code='DELIVERY_UNAVAILABLE',
        )

    # Lock order: wallet → month guest rows → delivery (see design D3).
    locked_delivery = _lock_delivery_for_guest_create(delivery.pk)
    if delivery_is_personal_meal_off(locked_delivery):
        raise GuestMealNotEligibleError(
            PERSONAL_MEAL_OFF_MESSAGE,
            code='PERSONAL_MEAL_OFF',
        )
    if locked_delivery.status != OrderDelivery.DeliveryStatus.SCHEDULED:
        raise GuestMealNotEligibleError(
            'A delivery stop is not available for this date and meal period.',
            code='DELIVERY_UNAVAILABLE',
        )

    metadata = {
        'purpose': GUEST_MEAL_PURPOSE,
        'service_date': service_date.isoformat(),
        'meal_period': meal_period,
        'quantity': quantity,
        'base_meal_price': f'{quote.base_meal_price:.2f}',
        'box_price': f'{quote.box_price:.2f}',
        'unit_price': f'{quote.unit_price:.2f}',
        'subscription_public_id': str(subscription.public_id),
    }

    try:
        txn = debit_wallet(
            locked_wallet,
            quote.total_amount,
            type=WalletTransaction.Type.PAYMENT,
            method=WalletTransaction.Method.MANUAL,
            status=WalletTransaction.Status.COMPLETED,
            note=f'Guest meal {service_date.isoformat()} {meal_period} x{quantity}',
            idempotency_key=key,
            metadata=metadata,
        )
    except InsufficientFundsError as exc:
        raise GuestMealWalletError(
            'Insufficient wallet balance for this guest meal.',
            code='INSUFFICIENT_FUNDS',
        ) from exc
    except WalletFrozenError as exc:
        raise GuestMealWalletError(
            'Your wallet is frozen. You cannot order guest meals until it is unfrozen.',
            code='WALLET_FROZEN',
        ) from exc
    except IntegrityError as exc:
        # Concurrent idempotency key race — reload original.
        if key:
            replay = _find_idempotent_order(customer, key)
            if replay is not None:
                if not _idempotency_payload_matches(
                    replay,
                    service_date=service_date,
                    meal_period=meal_period,
                    quantity=quantity,
                ):
                    raise GuestMealValidationError(
                        'Idempotency key was already used with a different guest meal payload.',
                        code='IDEMPOTENCY_CONFLICT',
                    ) from exc
                usage = guest_usage_summary(customer)
                payload = serialize_guest_meal_order(replay)
                payload.update(
                    {
                        'monthly_limit': usage['monthly_limit'],
                        'monthly_used': usage['used_quantity'],
                        'monthly_remaining': usage['remaining_quantity'],
                        'monthly_remaining_after_order': usage['remaining_quantity'],
                        'idempotent_replay': True,
                    }
                )
                return replay, payload
        raise GuestMealError(
            'Could not complete guest meal purchase.',
            code='GUEST_MEAL_CREATE_FAILED',
        ) from exc

    try:
        order = GuestMealOrder.objects.create(
            customer=customer,
            subscription=subscription,
            delivery=locked_delivery,
            service_date=service_date,
            meal_period=meal_period,
            quantity=quantity,
            base_meal_price=quote.base_meal_price,
            box_price=quote.box_price,
            unit_price=quote.unit_price,
            total_amount=quote.total_amount,
            status=GuestMealOrder.Status.SCHEDULED,
            wallet_transaction=txn,
            idempotency_key=key,
        )
    except IntegrityError as exc:
        if key:
            replay = _find_idempotent_order(customer, key)
            if replay is not None:
                usage = guest_usage_summary(customer)
                payload = serialize_guest_meal_order(replay)
                payload.update(
                    {
                        'monthly_limit': usage['monthly_limit'],
                        'monthly_used': usage['used_quantity'],
                        'monthly_remaining': usage['remaining_quantity'],
                        'monthly_remaining_after_order': usage['remaining_quantity'],
                        'idempotent_replay': True,
                    }
                )
                return replay, payload
        raise GuestMealError(
            'Could not complete guest meal purchase.',
            code='GUEST_MEAL_CREATE_FAILED',
        ) from exc

    from orders.services.wallet_balance_thresholds import evaluate_meal_stop_after_debit

    evaluate_meal_stop_after_debit(customer)

    usage = guest_usage_summary(customer)
    payload = serialize_guest_meal_order(order)
    payload.update(
        {
            'monthly_limit': usage['monthly_limit'],
            'monthly_used': usage['used_quantity'],
            'monthly_remaining': usage['remaining_quantity'],
            'monthly_remaining_after_order': usage['remaining_quantity'],
            'idempotent_replay': False,
        }
    )
    return order, payload


def sync_guest_meals_for_delivered_delivery(delivery: OrderDelivery) -> int:
    """
    Mark linked scheduled guest meals as delivered when the parent stop is delivered.

    Also idempotently recognizes Guest Meal profit for all delivered guest orders
    on this stop (no second wallet debit).
    """
    if delivery.status != OrderDelivery.DeliveryStatus.DELIVERED:
        return 0
    updated = (
        GuestMealOrder.objects.filter(
            delivery=delivery,
            status=GuestMealOrder.Status.SCHEDULED,
        ).update(status=GuestMealOrder.Status.DELIVERED)
    )
    from admin_wallet.services.profit_ledger import recognize_guest_meal_profit

    delivered_guests = (
        GuestMealOrder.objects.filter(
            delivery=delivery,
            status=GuestMealOrder.Status.DELIVERED,
        )
        .select_related('subscription__meal', 'customer', 'subscription')
    )
    for guest_order in delivered_guests:
        recognize_guest_meal_profit(guest_order)
    return updated

