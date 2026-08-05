from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from orders.models import MealOffSettings, Order, OrderDelivery
from orders.services.order_delivery import complete_order_if_done
from orders.services.order_status import OrderStatusError, reopen_order_after_meal_on


def get_meal_off_settings() -> MealOffSettings:
    return MealOffSettings.load()


def update_meal_off_settings(
    *,
    timezone_name: str | None = None,
    lunch_off_time: time | None = None,
    dinner_off_time: time | None = None,
) -> MealOffSettings:
    settings_obj = MealOffSettings.load()
    if timezone_name is not None:
        ZoneInfo(timezone_name)
        settings_obj.timezone = timezone_name
    if lunch_off_time is not None:
        settings_obj.lunch_off_time = lunch_off_time
    if dinner_off_time is not None:
        settings_obj.dinner_off_time = dinner_off_time
    settings_obj.save()
    return settings_obj


def meal_off_business_now(settings_obj: MealOffSettings | None = None) -> datetime:
    settings_obj = settings_obj or get_meal_off_settings()
    tz = ZoneInfo(settings_obj.timezone)
    return timezone.now().astimezone(tz)


def meal_off_deadline(
    service_date: date,
    meal_period: str,
    settings_obj: MealOffSettings | None = None,
) -> datetime:
    settings_obj = settings_obj or get_meal_off_settings()
    tz = ZoneInfo(settings_obj.timezone)
    if meal_period == OrderDelivery.MealPeriod.LUNCH:
        deadline_date = service_date - timedelta(days=1)
        deadline_time = settings_obj.lunch_off_time
    elif meal_period == OrderDelivery.MealPeriod.DINNER:
        deadline_date = service_date
        deadline_time = settings_obj.dinner_off_time
    else:
        raise ValueError(f'Unsupported meal period for meal-off: {meal_period}')
    return datetime.combine(deadline_date, deadline_time, tzinfo=tz)


def _normalize_business_now(
    now: datetime | None,
    settings_obj: MealOffSettings,
) -> datetime:
    now_local = now or meal_off_business_now(settings_obj)
    if now_local.tzinfo is None:
        return now_local.replace(tzinfo=ZoneInfo(settings_obj.timezone))
    return now_local.astimezone(ZoneInfo(settings_obj.timezone))


def _before_or_at_deadline(
    delivery: OrderDelivery,
    *,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
) -> bool:
    settings_obj = settings_obj or get_meal_off_settings()
    now_local = _normalize_business_now(now, settings_obj)
    deadline = meal_off_deadline(delivery.service_date, delivery.meal_period, settings_obj)
    return now_local <= deadline


def can_meal_off(
    delivery: OrderDelivery,
    *,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
) -> bool:
    if delivery.status != OrderDelivery.DeliveryStatus.SCHEDULED:
        return False
    order = delivery.order
    if order.order_status == Order.OrderStatus.CANCELLED:
        return False
    return _before_or_at_deadline(delivery, now=now, settings_obj=settings_obj)


def can_meal_on(
    delivery: OrderDelivery,
    *,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
) -> bool:
    if delivery.status != OrderDelivery.DeliveryStatus.SKIPPED:
        return False
    if delivery.skip_source != OrderDelivery.SkipSource.CUSTOMER:
        return False
    order = delivery.order
    if order.order_status == Order.OrderStatus.CANCELLED:
        return False
    return _before_or_at_deadline(delivery, now=now, settings_obj=settings_obj)


class MealOffError(Exception):
    pass


@transaction.atomic
def customer_meal_off(delivery: OrderDelivery, user, note: str = '') -> OrderDelivery:
    locked = (
        OrderDelivery.objects.select_for_update()
        .select_related('order', 'order__customer')
        .get(pk=delivery.pk)
    )
    order = locked.order
    profile = getattr(user, 'customer_profile', None)
    if profile is None or order.customer_id != profile.pk:
        raise MealOffError('Delivery not found for this order.')

    if order.order_status == Order.OrderStatus.CANCELLED:
        raise MealOffError('Cannot meal-off on a cancelled order.')

    if locked.status != OrderDelivery.DeliveryStatus.SCHEDULED:
        raise MealOffError(
            f'Delivery is already {locked.status} and cannot be meal-offed.'
        )

    settings_obj = get_meal_off_settings()
    now_local = meal_off_business_now(settings_obj)
    deadline = meal_off_deadline(locked.service_date, locked.meal_period, settings_obj)
    if now_local > deadline:
        raise MealOffError('Meal-off deadline has passed for this slot.')

    locked.status = OrderDelivery.DeliveryStatus.SKIPPED
    locked.skip_source = OrderDelivery.SkipSource.CUSTOMER
    locked.marked_by = user
    locked.marked_at = timezone.now()
    if note:
        locked.note = note
    locked.save(
        update_fields=[
            'status',
            'skip_source',
            'marked_by',
            'marked_at',
            'note',
            'updated_at',
        ]
    )

    try:
        complete_order_if_done(
            order,
            changed_by=user,
            note='Completed after customer meal-off.',
        )
    except OrderStatusError as exc:
        raise MealOffError(str(exc)) from exc

    locked.refresh_from_db()
    return locked


@transaction.atomic
def customer_meal_on(delivery: OrderDelivery, user, note: str = '') -> OrderDelivery:
    """
    Undo customer meal-off before the same deadline.

    Does not debit the wallet; charge happens only if later marked delivered.
    """
    locked = (
        OrderDelivery.objects.select_for_update()
        .select_related('order', 'order__customer')
        .get(pk=delivery.pk)
    )
    order = locked.order
    profile = getattr(user, 'customer_profile', None)
    if profile is None or order.customer_id != profile.pk:
        raise MealOffError('Delivery not found for this order.')

    if order.order_status == Order.OrderStatus.CANCELLED:
        raise MealOffError('Cannot meal-on on a cancelled order.')

    if locked.status != OrderDelivery.DeliveryStatus.SKIPPED:
        raise MealOffError(
            f'Delivery is {locked.status} and cannot be meal-oned.'
        )
    if locked.skip_source != OrderDelivery.SkipSource.CUSTOMER:
        raise MealOffError('Only customer meal-offs can be turned back on.')

    settings_obj = get_meal_off_settings()
    now_local = meal_off_business_now(settings_obj)
    deadline = meal_off_deadline(locked.service_date, locked.meal_period, settings_obj)
    if now_local > deadline:
        raise MealOffError('Meal-on deadline has passed for this slot.')

    locked.status = OrderDelivery.DeliveryStatus.SCHEDULED
    locked.skip_source = None
    locked.marked_by = None
    locked.marked_at = None
    update_fields = [
        'status',
        'skip_source',
        'marked_by',
        'marked_at',
        'updated_at',
    ]
    if note:
        locked.note = note
        update_fields.append('note')
    locked.save(update_fields=update_fields)

    try:
        reopen_order_after_meal_on(order, changed_by=user)
    except OrderStatusError as exc:
        raise MealOffError(str(exc)) from exc

    locked.refresh_from_db()
    return locked
