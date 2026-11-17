"""Test Meal trial orders for authenticated non-subscribers (no wallet debit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone

from meals.models import MealCategory
from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import (
    OrderDelivery,
    TestMealFunnelEvent,
    TestMealOrder,
    TestMealPaymentEvent,
)
from orders.services.delivery_address import snapshot_fields_from_place
from orders.services.meal_off import is_past_meal_cutoff
from orders.services.order_wallet_settings import get_order_wallet_settings
from orders.services.subscription_service import business_today, get_active_subscription
from service_area.services.verification import ServiceAreaError, assert_serviceable
from user_management.models import CustomerDeliveryPlace, CustomerProfile

MONEY = Decimal('0.01')
CURRENCY = 'BDT'

DELIVERY_WINDOWS = {
    TestMealOrder.MealPeriod.LUNCH: (time(11, 0), time(14, 0)),
    TestMealOrder.MealPeriod.DINNER: (time(19, 30), time(22, 30)),
}

QUOTA_EXHAUSTED_BN = (
    'আপনার ২টি টেস্ট মিল কোটা শেষ হয়ে গেছে। অনুগ্রহ করে সাবস্ক্রাইব করুন।'
)
QUOTA_EXHAUSTED_EN = (
    'Your two Test Meal quota is finished. Please subscribe to continue.'
)
ACTIVE_SUBSCRIBER_BN = (
    'আপনার একটি সক্রিয় সাবস্ক্রিপশন আছে। টেস্ট মিল শুধুমাত্র নন-সাবস্ক্রাইবারদের জন্য।'
)
ACTIVE_SUBSCRIBER_EN = (
    'You already have an active subscription. Test Meals are for non-subscribers.'
)

# Accepted rows consume lifetime quota (including later cancel/deliver/fail).
QUOTA_STATUSES = tuple(TestMealOrder.OrderStatus.values)
COOKING_STATUSES = (
    TestMealOrder.OrderStatus.CONFIRMED,
    TestMealOrder.OrderStatus.PREPARING,
    TestMealOrder.OrderStatus.OUT_FOR_DELIVERY,
    TestMealOrder.OrderStatus.DELIVERED,
)

ORDER_STATUS_TRANSITIONS = {
    TestMealOrder.OrderStatus.CONFIRMED: {
        TestMealOrder.OrderStatus.PREPARING,
        TestMealOrder.OrderStatus.OUT_FOR_DELIVERY,
        TestMealOrder.OrderStatus.DELIVERED,
        TestMealOrder.OrderStatus.CANCELLED,
        TestMealOrder.OrderStatus.FAILED,
    },
    TestMealOrder.OrderStatus.PREPARING: {
        TestMealOrder.OrderStatus.OUT_FOR_DELIVERY,
        TestMealOrder.OrderStatus.DELIVERED,
        TestMealOrder.OrderStatus.CANCELLED,
        TestMealOrder.OrderStatus.FAILED,
    },
    TestMealOrder.OrderStatus.OUT_FOR_DELIVERY: {
        TestMealOrder.OrderStatus.DELIVERED,
        TestMealOrder.OrderStatus.FAILED,
        TestMealOrder.OrderStatus.CANCELLED,
    },
    TestMealOrder.OrderStatus.DELIVERED: set(),
    TestMealOrder.OrderStatus.CANCELLED: set(),
    TestMealOrder.OrderStatus.FAILED: set(),
}


class TestMealError(Exception):
    def __init__(self, message: str, *, code: str = 'TEST_MEAL_ERROR'):
        super().__init__(message)
        self.code = code


class TestMealNotEligibleError(TestMealError):
    pass


class TestMealValidationError(TestMealError):
    pass


class TestMealQuotaError(TestMealError):
    pass


@dataclass(frozen=True)
class TestMealQuote:
    service_date: date
    meal_period: str
    package_public_id: str
    package_name: str
    meal_price: Decimal
    box_charge: Decimal
    total_price: Decimal
    currency: str
    delivery_window_start: time
    delivery_window_end: time
    cutoff_passed: bool


def _quantize(amount: Decimal) -> Decimal:
    return Decimal(amount).quantize(MONEY)


def parse_test_meal_period(raw: str) -> str:
    if raw not in TestMealOrder.MealPeriod.values:
        raise TestMealValidationError(
            'meal_period must be lunch or dinner.',
            code='INVALID_MEAL_PERIOD',
        )
    return raw


def delivery_window_for(meal_period: str) -> tuple[time, time]:
    return DELIVERY_WINDOWS[meal_period]


def lifetime_quota_used(customer: CustomerProfile, *, exclude_pk: int | None = None) -> int:
    qs = TestMealOrder.objects.filter(customer=customer, order_status__in=QUOTA_STATUSES)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.count()


def lifetime_quota_limit() -> int:
    return int(get_order_wallet_settings().test_meal_lifetime_quota)


def eligibility_for_customer(customer: CustomerProfile) -> dict[str, Any]:
    limit = lifetime_quota_limit()
    used = lifetime_quota_used(customer)
    remaining = max(limit - used, 0)
    active_sub = get_active_subscription(customer) is not None

    reason = None
    message_bn = None
    message_en = None
    eligible = True

    if active_sub:
        eligible = False
        reason = 'ACTIVE_SUBSCRIBER'
        message_bn = ACTIVE_SUBSCRIBER_BN
        message_en = ACTIVE_SUBSCRIBER_EN
    elif remaining <= 0:
        eligible = False
        reason = 'QUOTA_EXHAUSTED'
        message_bn = QUOTA_EXHAUSTED_BN
        message_en = QUOTA_EXHAUSTED_EN

    return {
        'eligible': eligible,
        'is_active_subscriber': active_sub,
        'quota_limit': limit,
        'quota_used': used,
        'quota_remaining': remaining,
        'reason': reason,
        'message_bn': message_bn,
        'message_en': message_en,
        'currency': CURRENCY,
        'delivery_windows': {
            'lunch': {
                'start': DELIVERY_WINDOWS[TestMealOrder.MealPeriod.LUNCH][0].strftime('%H:%M'),
                'end': DELIVERY_WINDOWS[TestMealOrder.MealPeriod.LUNCH][1].strftime('%H:%M'),
            },
            'dinner': {
                'start': DELIVERY_WINDOWS[TestMealOrder.MealPeriod.DINNER][0].strftime('%H:%M'),
                'end': DELIVERY_WINDOWS[TestMealOrder.MealPeriod.DINNER][1].strftime('%H:%M'),
            },
        },
    }


def assert_eligible_for_create(customer: CustomerProfile) -> dict[str, Any]:
    eligibility = eligibility_for_customer(customer)
    if eligibility['reason'] == 'ACTIVE_SUBSCRIBER':
        raise TestMealNotEligibleError(
            eligibility['message_en'] or ACTIVE_SUBSCRIBER_EN,
            code='ACTIVE_SUBSCRIBER',
        )
    if eligibility['reason'] == 'QUOTA_EXHAUSTED':
        raise TestMealQuotaError(
            eligibility['message_bn'] or QUOTA_EXHAUSTED_BN,
            code='QUOTA_EXHAUSTED',
        )
    return eligibility


def list_test_meal_packages() -> list[MealCategory]:
    return list(
        MealCategory.objects.filter(is_active=True, is_subscribable=True).order_by(
            'meal_name', 'id'
        )
    )


def resolve_package(package_public_id) -> MealCategory:
    try:
        package = MealCategory.objects.get(public_id=package_public_id)
    except (MealCategory.DoesNotExist, ValueError, TypeError) as exc:
        raise TestMealValidationError(
            'Package not found.',
            code='PACKAGE_NOT_FOUND',
        ) from exc
    if not package.is_active or not package.is_subscribable:
        raise TestMealValidationError(
            'Package is not available for Test Meal ordering.',
            code='PACKAGE_UNAVAILABLE',
        )
    return package


def resolve_test_meal_pricing(
    *,
    meal_id: int,
    service_date: date,
    meal_period: str,
) -> tuple[Decimal, Decimal, Decimal]:
    settings_obj = get_order_wallet_settings()
    slot = resolve_published_slot_for_delivery(
        meal_id=meal_id,
        service_date=service_date,
        meal_period=meal_period,
    )
    if slot is None or slot.final_meal_price_snapshot is None:
        raise TestMealValidationError(
            'Meal price is unavailable for this date and meal period.',
            code='PRICE_UNAVAILABLE',
        )
    meal_price = _quantize(Decimal(slot.final_meal_price_snapshot))
    box_charge = _quantize(Decimal(settings_obj.test_meal_box_price))
    total = _quantize(meal_price + box_charge)
    return meal_price, box_charge, total


def validate_service_slot(*, service_date: date, meal_period: str) -> None:
    today = business_today()
    if service_date < today:
        raise TestMealValidationError(
            'service_date cannot be in the past.',
            code='INVALID_DATE',
        )
    if is_past_meal_cutoff(service_date=service_date, meal_period=meal_period):
        raise TestMealValidationError(
            'Ordering cutoff for this meal period has passed.',
            code='CUTOFF_PASSED',
        )


def build_test_meal_quote(
    customer: CustomerProfile,
    *,
    service_date: date,
    meal_period: str,
    package_public_id,
) -> TestMealQuote:
    assert_eligible_for_create(customer)
    meal_period = parse_test_meal_period(meal_period)
    validate_service_slot(service_date=service_date, meal_period=meal_period)
    package = resolve_package(package_public_id)
    meal_price, box_charge, total = resolve_test_meal_pricing(
        meal_id=package.pk,
        service_date=service_date,
        meal_period=meal_period,
    )
    window_start, window_end = delivery_window_for(meal_period)
    return TestMealQuote(
        service_date=service_date,
        meal_period=meal_period,
        package_public_id=str(package.public_id),
        package_name=package.meal_name,
        meal_price=meal_price,
        box_charge=box_charge,
        total_price=total,
        currency=CURRENCY,
        delivery_window_start=window_start,
        delivery_window_end=window_end,
        cutoff_passed=False,
    )


def quote_to_dict(quote: TestMealQuote) -> dict[str, Any]:
    return {
        'service_date': quote.service_date.isoformat(),
        'meal_period': quote.meal_period,
        'package_public_id': quote.package_public_id,
        'package_name': quote.package_name,
        'meal_price': str(quote.meal_price),
        'box_charge': str(quote.box_charge),
        'total_price': str(quote.total_price),
        'currency': quote.currency,
        'delivery_window_start': quote.delivery_window_start.strftime('%H:%M'),
        'delivery_window_end': quote.delivery_window_end.strftime('%H:%M'),
        'cutoff_passed': quote.cutoff_passed,
    }


def _resolve_owned_address(
    customer: CustomerProfile,
    address_public_id,
) -> CustomerDeliveryPlace:
    try:
        place = CustomerDeliveryPlace.objects.get(
            public_id=address_public_id,
            customer_profile=customer,
        )
    except (CustomerDeliveryPlace.DoesNotExist, ValueError, TypeError) as exc:
        raise TestMealValidationError(
            'Delivery address not found.',
            code='ADDRESS_NOT_FOUND',
        ) from exc
    if not place.is_active:
        raise TestMealValidationError(
            'Delivery address is inactive.',
            code='ADDRESS_INACTIVE',
        )
    # Subscription-style manual places may omit coordinates. Only enforce
    # geo serviceability when at least one coordinate is present so
    # out-of-zone places still fail while null-coord owned places work.
    if place.latitude is not None or place.longitude is not None:
        try:
            assert_serviceable(place.latitude, place.longitude)
        except ServiceAreaError as exc:
            raise TestMealValidationError(str(exc), code=exc.code) from exc
    return place


def _idempotency_payload_matches(
    order: TestMealOrder,
    *,
    service_date: date,
    meal_period: str,
    package_id: int,
    address_id: int,
    special_instructions: str,
) -> bool:
    return (
        order.service_date == service_date
        and order.meal_period == meal_period
        and order.package_id == package_id
        and order.address_id == address_id
        and (order.special_instructions or '') == (special_instructions or '')
    )


def _find_idempotent_order(customer: CustomerProfile, key: str | None):
    if not key:
        return None
    return (
        TestMealOrder.objects.filter(customer=customer, idempotency_key=key)
        .select_related('package', 'address')
        .first()
    )


def serialize_test_meal_order(
    order: TestMealOrder,
    *,
    idempotent_replay: bool = False,
) -> dict[str, Any]:
    payload = {
        'public_id': str(order.public_id),
        'service_date': order.service_date.isoformat(),
        'meal_period': order.meal_period,
        'package_public_id': str(order.package.public_id) if order.package_id else None,
        'package_name': order.package_name_snapshot or (
            order.package.meal_name if order.package_id else ''
        ),
        'special_instructions': order.special_instructions or '',
        'meal_price': str(order.meal_price),
        'box_charge': str(order.box_charge),
        'total_price': str(order.total_price),
        'currency': order.currency,
        'order_status': order.order_status,
        'payment_status': order.payment_status,
        'payment_method': order.payment_method,
        'delivery_window_start': order.delivery_window_start.strftime('%H:%M'),
        'delivery_window_end': order.delivery_window_end.strftime('%H:%M'),
        'address': {
            'public_id': str(order.address.public_id) if order.address_id else None,
            'label': order.address_label_snapshot,
            'full_address': order.address_full_snapshot,
            'area': order.address_area_snapshot,
            'city': order.address_city_snapshot,
        },
        'created_at': order.created_at.isoformat().replace('+00:00', 'Z')
        if order.created_at
        else None,
        'delivered_at': order.delivered_at.isoformat().replace('+00:00', 'Z')
        if order.delivered_at
        else None,
        'cancelled_at': order.cancelled_at.isoformat().replace('+00:00', 'Z')
        if order.cancelled_at
        else None,
    }
    if idempotent_replay:
        payload['idempotent_replay'] = True
    return payload


def _resolve_customer_zone_location(customer: CustomerProfile):
    sub = getattr(customer, 'delivery_sub_location', None)
    if sub is not None:
        location = sub.location
        return getattr(location, 'zone', None), location, sub
    location = getattr(customer, 'delivery_location', None)
    if location is None:
        return None, None, None
    return getattr(location, 'zone', None), location, None


def _create_fulfillment_stop(order: TestMealOrder, place: CustomerDeliveryPlace) -> OrderDelivery:
    delivery = OrderDelivery(
        order=None,
        subscription=None,
        test_meal_order=order,
        service_date=order.service_date,
        meal_period=order.meal_period,
        status=OrderDelivery.DeliveryStatus.SCHEDULED,
        payment_status=OrderDelivery.PaymentStatus.NOT_APPLICABLE,
    )
    apply_fields = snapshot_fields_from_place(place)
    for key, value in apply_fields.items():
        setattr(delivery, key, value)

    zone, location, sub = _resolve_customer_zone_location(order.customer)
    delivery.logistics_zone = zone
    delivery.logistics_location = location
    delivery.logistics_sub_location = sub
    delivery.save()
    return delivery


@transaction.atomic
def create_test_meal_order(
    customer: CustomerProfile,
    *,
    service_date: date,
    meal_period: str,
    package_public_id,
    address_public_id,
    special_instructions: str = '',
    source_channel: str = '',
    idempotency_key: str | None = None,
) -> tuple[TestMealOrder, dict[str, Any]]:
    meal_period = parse_test_meal_period(meal_period)
    special_instructions = (special_instructions or '').strip()
    source_channel = (source_channel or '').strip()[:64]
    key = (idempotency_key or '').strip() or None

    package = resolve_package(package_public_id)
    place = _resolve_owned_address(customer, address_public_id)

    existing = _find_idempotent_order(customer, key)
    if existing is not None:
        if not _idempotency_payload_matches(
            existing,
            service_date=service_date,
            meal_period=meal_period,
            package_id=package.pk,
            address_id=place.pk,
            special_instructions=special_instructions,
        ):
            raise TestMealValidationError(
                'Idempotency-Key was reused with a different Test Meal payload.',
                code='IDEMPOTENCY_CONFLICT',
            )
        return existing, serialize_test_meal_order(existing, idempotent_replay=True)

    # Serialize concurrent creates for the same customer.
    CustomerProfile.objects.select_for_update().get(pk=customer.pk)
    list(
        TestMealOrder.objects.select_for_update()
        .filter(customer=customer)
        .order_by('id')
    )

    assert_eligible_for_create(customer)
    validate_service_slot(service_date=service_date, meal_period=meal_period)
    meal_price, box_charge, total = resolve_test_meal_pricing(
        meal_id=package.pk,
        service_date=service_date,
        meal_period=meal_period,
    )
    window_start, window_end = delivery_window_for(meal_period)
    place_snap = snapshot_fields_from_place(place)

    try:
        order = TestMealOrder.objects.create(
            customer=customer,
            package=package,
            package_name_snapshot=package.meal_name,
            service_date=service_date,
            meal_period=meal_period,
            special_instructions=special_instructions,
            meal_price=meal_price,
            box_charge=box_charge,
            total_price=total,
            currency=CURRENCY,
            address=place,
            address_label_snapshot=place_snap['delivery_label_snapshot'],
            address_full_snapshot=place_snap['delivery_full_address_snapshot'],
            address_area_snapshot=place_snap['delivery_area_snapshot'],
            address_city_snapshot=place_snap['delivery_city_snapshot'],
            address_building_name_snapshot=place_snap['delivery_building_name_snapshot'],
            address_floor_snapshot=place_snap['delivery_floor_snapshot'],
            address_flat_number_snapshot=place_snap['delivery_flat_number_snapshot'],
            address_latitude_snapshot=place_snap['delivery_latitude_snapshot'],
            address_longitude_snapshot=place_snap['delivery_longitude_snapshot'],
            delivery_window_start=window_start,
            delivery_window_end=window_end,
            order_status=TestMealOrder.OrderStatus.CONFIRMED,
            payment_status=TestMealOrder.PaymentStatus.UNPAID,
            payment_method=TestMealOrder.PaymentMethod.MANUAL,
            source_channel=source_channel,
            idempotency_key=key,
        )
    except IntegrityError:
        existing = _find_idempotent_order(customer, key)
        if existing is not None:
            return existing, serialize_test_meal_order(existing, idempotent_replay=True)
        raise

    _create_fulfillment_stop(order, place)
    return order, serialize_test_meal_order(order, idempotent_replay=False)


def transition_test_meal_order_status(
    order: TestMealOrder,
    *,
    to_status: str,
    reason: str = '',
) -> TestMealOrder:
    if to_status not in TestMealOrder.OrderStatus.values:
        raise TestMealValidationError(
            'Invalid order status.',
            code='INVALID_ORDER_STATUS',
        )
    allowed = ORDER_STATUS_TRANSITIONS.get(order.order_status, set())
    if to_status not in allowed:
        raise TestMealValidationError(
            f'Cannot transition from {order.order_status} to {to_status}.',
            code='INVALID_STATUS_TRANSITION',
        )
    order.order_status = to_status
    update_fields = ['order_status', 'updated_at']
    if to_status == TestMealOrder.OrderStatus.DELIVERED:
        order.delivered_at = timezone.now()
        update_fields.append('delivered_at')
    if to_status == TestMealOrder.OrderStatus.CANCELLED:
        order.cancelled_at = timezone.now()
        order.cancellation_reason = (reason or '').strip()
        update_fields.extend(['cancelled_at', 'cancellation_reason'])
        OrderDelivery.objects.filter(
            test_meal_order=order,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        ).update(
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.ADMIN,
            updated_at=timezone.now(),
        )
    order.save(update_fields=update_fields)
    return order


def sync_test_meal_for_delivered_delivery(delivery: OrderDelivery) -> TestMealOrder | None:
    """Mark linked Test Meal delivered without wallet charge."""
    if not delivery.test_meal_order_id:
        return None
    order = (
        TestMealOrder.objects.select_for_update()
        .filter(pk=delivery.test_meal_order_id)
        .first()
    )
    if order is None:
        return None
    if order.order_status == TestMealOrder.OrderStatus.DELIVERED:
        return order
    if order.order_status in (
        TestMealOrder.OrderStatus.CANCELLED,
        TestMealOrder.OrderStatus.FAILED,
    ):
        return order
    order.order_status = TestMealOrder.OrderStatus.DELIVERED
    order.delivered_at = delivery.delivered_at or timezone.now()
    order.save(update_fields=['order_status', 'delivered_at', 'updated_at'])
    return order


def test_cooking_quantities_by_package(
    *,
    service_date: date,
    meal_period: str,
) -> dict[int, int]:
    rows = (
        TestMealOrder.objects.filter(
            service_date=service_date,
            meal_period=meal_period,
            order_status__in=COOKING_STATUSES,
        )
        .values('package_id')
        .annotate(total=Count('id'))
    )
    return {
        int(row['package_id']): int(row['total'] or 0)
        for row in rows
        if row['package_id'] is not None
    }


def test_meal_quantities_by_delivery_ids(delivery_ids: list[int]) -> dict[int, int]:
    if not delivery_ids:
        return {}
    rows = (
        OrderDelivery.objects.filter(
            pk__in=delivery_ids,
            test_meal_order_id__isnull=False,
            test_meal_order__order_status__in=COOKING_STATUSES,
        )
        .values('id')
        .annotate(total=Count('test_meal_order_id'))
    )
    return {int(row['id']): int(row['total'] or 0) for row in rows}


def customer_test_meal_queryset(customer: CustomerProfile):
    return (
        TestMealOrder.objects.filter(customer=customer)
        .select_related('package', 'address')
        .order_by('-created_at', '-id')
    )


def admin_test_meal_queryset():
    return (
        TestMealOrder.objects.select_related(
            'customer',
            'customer__user',
            'customer__delivery_location',
            'customer__delivery_location__zone',
            'customer__delivery_sub_location',
            'customer__delivery_sub_location__location__zone',
            'package',
            'address',
            'payment_recorded_by',
        )
        .prefetch_related('deliveries')
        .order_by('-created_at', '-id')
    )


def conversion_flags_for_order(order: TestMealOrder) -> dict[str, Any]:
    from orders.models import CustomerSubscription

    has_active = get_active_subscription(order.customer) is not None
    first_delivered = (
        TestMealOrder.objects.filter(
            customer=order.customer,
            order_status=TestMealOrder.OrderStatus.DELIVERED,
        )
        .order_by('delivered_at', 'id')
        .first()
    )
    first_sub = (
        CustomerSubscription.objects.filter(customer=order.customer)
        .order_by('started_on', 'created_at', 'id')
        .first()
    )
    historically_converted = False
    if first_delivered and first_delivered.delivered_at and first_sub is not None:
        sub_start = first_sub.started_on or (
            first_sub.created_at.date() if first_sub.created_at else None
        )
        delivered_on = first_delivered.delivered_at.date()
        if sub_start and sub_start >= delivered_on:
            historically_converted = True
    return {
        'is_currently_active_subscriber': has_active,
        'has_subscribed_after_test': historically_converted,
    }


def serialize_admin_test_meal_order(order: TestMealOrder) -> dict[str, Any]:
    flags = conversion_flags_for_order(order)
    delivery = order.deliveries.order_by('id').first() if hasattr(order, 'deliveries') else None
    zone = None
    if delivery and delivery.logistics_zone_id:
        zone = {
            'public_id': str(delivery.logistics_zone.public_id),
            'name': delivery.logistics_zone.name,
            'code': getattr(delivery.logistics_zone, 'code', '') or '',
        }
    customer = order.customer
    user = customer.user
    return {
        'public_id': str(order.public_id),
        'customer': {
            'public_id': str(customer.public_id),
            'name': f'{user.first_name} {user.last_name}'.strip() or user.email,
            'phone': customer.phone or '',
            'email': user.email or '',
        },
        'package_public_id': str(order.package.public_id) if order.package_id else None,
        'package_name': order.package_name_snapshot or (
            order.package.meal_name if order.package_id else ''
        ),
        'service_date': order.service_date.isoformat(),
        'meal_period': order.meal_period,
        'delivery_window_start': order.delivery_window_start.strftime('%H:%M'),
        'delivery_window_end': order.delivery_window_end.strftime('%H:%M'),
        'address': {
            'label': order.address_label_snapshot,
            'full_address': order.address_full_snapshot,
            'area': order.address_area_snapshot,
            'city': order.address_city_snapshot,
        },
        'zone': zone,
        'meal_price': str(order.meal_price),
        'box_charge': str(order.box_charge),
        'total_price': str(order.total_price),
        'currency': order.currency,
        'order_status': order.order_status,
        'payment_status': order.payment_status,
        'payment_method': order.payment_method,
        'amount_collected': str(order.amount_collected)
        if order.amount_collected is not None
        else None,
        'paid_at': order.paid_at.isoformat().replace('+00:00', 'Z') if order.paid_at else None,
        'payment_notes': order.payment_notes or '',
        'special_instructions': order.special_instructions or '',
        'created_at': order.created_at.isoformat().replace('+00:00', 'Z')
        if order.created_at
        else None,
        'delivered_at': order.delivered_at.isoformat().replace('+00:00', 'Z')
        if order.delivered_at
        else None,
        'cancelled_at': order.cancelled_at.isoformat().replace('+00:00', 'Z')
        if order.cancelled_at
        else None,
        **flags,
    }


@transaction.atomic
def record_test_meal_payment(
    order: TestMealOrder,
    *,
    actor,
    amount: Decimal | None = None,
    collected_at=None,
    notes: str = '',
) -> TestMealOrder:
    locked = TestMealOrder.objects.select_for_update().get(pk=order.pk)
    if locked.payment_status == TestMealOrder.PaymentStatus.PAID:
        # Idempotent: do not double-count collected revenue.
        return locked
    if locked.payment_status == TestMealOrder.PaymentStatus.REFUNDED:
        raise TestMealValidationError(
            'Refunded orders cannot be marked paid without a correction.',
            code='INVALID_PAYMENT_STATE',
        )
    collected = _quantize(Decimal(amount if amount is not None else locked.total_price))
    before_status = locked.payment_status
    before_amount = locked.amount_collected
    locked.payment_status = TestMealOrder.PaymentStatus.PAID
    locked.amount_collected = collected
    locked.paid_at = collected_at or timezone.now()
    locked.payment_notes = (notes or '').strip()
    locked.payment_recorded_by = actor
    locked.save(
        update_fields=[
            'payment_status',
            'amount_collected',
            'paid_at',
            'payment_notes',
            'payment_recorded_by',
            'updated_at',
        ]
    )
    TestMealPaymentEvent.objects.create(
        order=locked,
        action=TestMealPaymentEvent.Action.RECORD,
        actor=actor,
        before_payment_status=before_status,
        after_payment_status=locked.payment_status,
        before_amount_collected=before_amount,
        after_amount_collected=locked.amount_collected,
        notes=locked.payment_notes,
    )
    return locked


@transaction.atomic
def correct_test_meal_payment(
    order: TestMealOrder,
    *,
    actor,
    payment_status: str,
    amount: Decimal | None = None,
    collected_at=None,
    notes: str = '',
) -> TestMealOrder:
    if payment_status not in TestMealOrder.PaymentStatus.values:
        raise TestMealValidationError(
            'Invalid payment status.',
            code='INVALID_PAYMENT_STATUS',
        )
    locked = TestMealOrder.objects.select_for_update().get(pk=order.pk)
    before_status = locked.payment_status
    before_amount = locked.amount_collected
    locked.payment_status = payment_status
    if amount is not None:
        locked.amount_collected = _quantize(Decimal(amount))
    if collected_at is not None:
        locked.paid_at = collected_at
    if payment_status == TestMealOrder.PaymentStatus.UNPAID:
        locked.amount_collected = None
        locked.paid_at = None
    locked.payment_notes = (notes or '').strip() or locked.payment_notes
    locked.payment_recorded_by = actor
    locked.save(
        update_fields=[
            'payment_status',
            'amount_collected',
            'paid_at',
            'payment_notes',
            'payment_recorded_by',
            'updated_at',
        ]
    )
    action = (
        TestMealPaymentEvent.Action.REFUND
        if payment_status == TestMealOrder.PaymentStatus.REFUNDED
        else TestMealPaymentEvent.Action.CORRECT
    )
    TestMealPaymentEvent.objects.create(
        order=locked,
        action=action,
        actor=actor,
        before_payment_status=before_status,
        after_payment_status=locked.payment_status,
        before_amount_collected=before_amount,
        after_amount_collected=locked.amount_collected,
        notes=notes or '',
    )
    return locked


def ingest_funnel_event(
    *,
    event_name: str,
    client_event_id: str,
    customer: CustomerProfile | None = None,
    correlation_id: str = '',
    metadata: dict | None = None,
) -> tuple[TestMealFunnelEvent, bool]:
    event_name = (event_name or '').strip()[:64]
    client_event_id = (client_event_id or '').strip()[:64]
    correlation_id = (correlation_id or '').strip()[:64]
    if not event_name or not client_event_id:
        raise TestMealValidationError(
            'event_name and client_event_id are required.',
            code='INVALID_FUNNEL_EVENT',
        )
    defaults = {
        'correlation_id': correlation_id,
        'metadata': metadata or {},
    }
    try:
        if customer is not None:
            obj, created = TestMealFunnelEvent.objects.get_or_create(
                event_name=event_name,
                client_event_id=client_event_id,
                customer=customer,
                defaults=defaults,
            )
        else:
            obj, created = TestMealFunnelEvent.objects.get_or_create(
                event_name=event_name,
                client_event_id=client_event_id,
                correlation_id=correlation_id,
                customer=None,
                defaults={'metadata': metadata or {}},
            )
        return obj, created
    except IntegrityError:
        existing = TestMealFunnelEvent.objects.filter(
            event_name=event_name,
            client_event_id=client_event_id,
        ).first()
        if existing is None:
            raise
        return existing, False


def build_test_meal_analytics(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    qs = TestMealOrder.objects.all()
    if date_from:
        qs = qs.filter(service_date__gte=date_from)
    if date_to:
        qs = qs.filter(service_date__lte=date_to)

    confirmed_value = _quantize(
        Decimal(qs.aggregate(total=Sum('total_price'))['total'] or 0)
    )
    paid_qs = qs.filter(payment_status=TestMealOrder.PaymentStatus.PAID)
    collected_value = _quantize(
        Decimal(paid_qs.aggregate(total=Sum('amount_collected'))['total'] or 0)
    )
    unpaid_qs = qs.filter(payment_status=TestMealOrder.PaymentStatus.UNPAID)
    outstanding_value = _quantize(
        Decimal(unpaid_qs.aggregate(total=Sum('total_price'))['total'] or 0)
    )
    delivered_unpaid = qs.filter(
        order_status=TestMealOrder.OrderStatus.DELIVERED,
        payment_status=TestMealOrder.PaymentStatus.UNPAID,
    ).count()

    delivered_customers = set(
        qs.filter(order_status=TestMealOrder.OrderStatus.DELIVERED)
        .values_list('customer_id', flat=True)
        .distinct()
    )
    from orders.models import CustomerSubscription

    after_delivery_converted = 0
    pre_delivery_subscribed = 0
    for customer_id in delivered_customers:
        first_delivered = (
            qs.filter(
                customer_id=customer_id,
                order_status=TestMealOrder.OrderStatus.DELIVERED,
                delivered_at__isnull=False,
            )
            .order_by('delivered_at', 'id')
            .first()
        )
        if first_delivered is None or first_delivered.delivered_at is None:
            continue
        first_sub = (
            CustomerSubscription.objects.filter(customer_id=customer_id)
            .order_by('started_on', 'created_at', 'id')
            .first()
        )
        if first_sub is None:
            continue
        sub_start = first_sub.started_on or (
            first_sub.created_at.date() if first_sub.created_at else None
        )
        if sub_start is None:
            continue
        delivered_on = first_delivered.delivered_at.date()
        if sub_start < delivered_on:
            pre_delivery_subscribed += 1
        elif sub_start >= delivered_on:
            after_delivery_converted += 1

    denominator = len(delivered_customers)
    primary_rate = (
        round((after_delivery_converted / denominator) * 100, 2) if denominator else 0.0
    )

    # Daily series
    daily = {}
    for row in qs.values('service_date').annotate(
        orders=Count('id'),
        revenue=Sum('total_price'),
    ):
        key = row['service_date'].isoformat()
        daily[key] = {
            'date': key,
            'orders': int(row['orders'] or 0),
            'confirmed_value': str(_quantize(Decimal(row['revenue'] or 0))),
            'deliveries': 0,
            'conversions': 0,
        }
    for row in qs.filter(order_status=TestMealOrder.OrderStatus.DELIVERED).values(
        'service_date'
    ).annotate(deliveries=Count('id')):
        key = row['service_date'].isoformat()
        daily.setdefault(
            key,
            {
                'date': key,
                'orders': 0,
                'confirmed_value': '0.00',
                'deliveries': 0,
                'conversions': 0,
            },
        )
        daily[key]['deliveries'] = int(row['deliveries'] or 0)

    package_popularity = [
        {
            'package_public_id': str(row['package__public_id']),
            'package_name': row['package_name_snapshot'] or row['package__meal_name'],
            'order_count': int(row['orders'] or 0),
        }
        for row in qs.values(
            'package__public_id', 'package_name_snapshot', 'package__meal_name'
        ).annotate(orders=Count('id')).order_by('-orders')
    ]

    lunch_count = qs.filter(meal_period=TestMealOrder.MealPeriod.LUNCH).count()
    dinner_count = qs.filter(meal_period=TestMealOrder.MealPeriod.DINNER).count()

    return {
        'order_count': qs.count(),
        'customer_count': qs.values('customer_id').distinct().count(),
        'quota_limit_default': lifetime_quota_limit(),
        'confirmed_order_value': str(confirmed_value),
        'collected_revenue': str(collected_value),
        'outstanding_amount': str(outstanding_value),
        'unpaid_order_count': unpaid_qs.count(),
        'paid_order_count': paid_qs.count(),
        'delivered_unpaid_order_count': delivered_unpaid,
        'delivered_customer_count': denominator,
        'after_delivery_converted_customer_count': after_delivery_converted,
        'pre_delivery_subscribed_customer_count': pre_delivery_subscribed,
        'primary_conversion_rate': primary_rate,
        'period_distribution': {
            'lunch': lunch_count,
            'dinner': dinner_count,
        },
        'package_popularity': package_popularity,
        'daily_series': [daily[k] for k in sorted(daily.keys())],
        'funnel_event_count': TestMealFunnelEvent.objects.count(),
        'revenue_notes': {
            'confirmed_order_value': 'Sum of confirmed Test Meal totals in range.',
            'collected_revenue': 'Sum of amount_collected for paid orders.',
            'outstanding_amount': 'Sum of totals for unpaid confirmed orders.',
            'delivered_unpaid_order_count': 'Delivered orders still unpaid.',
        },
    }
