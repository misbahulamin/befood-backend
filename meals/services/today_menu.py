from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.utils import timezone

from meals.models import MenuRevealSettings, MonthlyMenuSchedule, MonthlyMenuSlot
from orders.models import Order


def get_reveal_settings() -> MenuRevealSettings:
    return MenuRevealSettings.load()


def update_reveal_settings(
    *,
    timezone_name: str | None = None,
    lunch_reveal_time: time | None = None,
    dinner_reveal_time: time | None = None,
) -> MenuRevealSettings:
    settings_obj = MenuRevealSettings.load()
    if timezone_name is not None:
        # Validate IANA timezone
        ZoneInfo(timezone_name)
        settings_obj.timezone = timezone_name
    if lunch_reveal_time is not None:
        settings_obj.lunch_reveal_time = lunch_reveal_time
    if dinner_reveal_time is not None:
        settings_obj.dinner_reveal_time = dinner_reveal_time
    settings_obj.save()
    return settings_obj


def business_now(settings_obj: MenuRevealSettings | None = None) -> datetime:
    settings_obj = settings_obj or get_reveal_settings()
    tz = ZoneInfo(settings_obj.timezone)
    return timezone.now().astimezone(tz)


def visible_periods_for_now(
    settings_obj: MenuRevealSettings | None = None,
    now: datetime | None = None,
) -> tuple[date, list[str]]:
    settings_obj = settings_obj or get_reveal_settings()
    now_local = now or business_now(settings_obj)
    today = now_local.date()
    visible: list[str] = []
    if now_local.time() >= settings_obj.lunch_reveal_time:
        visible.append(MonthlyMenuSlot.MealPeriod.LUNCH)
    if now_local.time() >= settings_obj.dinner_reveal_time:
        visible.append(MonthlyMenuSlot.MealPeriod.DINNER)
    return today, visible


def active_orders_for_customer_on_date(customer_profile, service_date: date):
    return (
        Order.objects.filter(
            customer=customer_profile,
            order_start_date__lte=service_date,
            order_end_date__gte=service_date,
        )
        .exclude(order_status=Order.OrderStatus.CANCELLED)
        .select_related('meal')
    )


def build_today_menu_for_customer(customer_profile, now: datetime | None = None) -> dict:
    settings_obj = get_reveal_settings()
    today, visible_periods = visible_periods_for_now(settings_obj, now=now)
    orders = list(active_orders_for_customer_on_date(customer_profile, today))

    packages = []
    for order in orders:
        schedule = (
            MonthlyMenuSchedule.objects.filter(
                plan__meal_category_id=order.meal_id,
                plan__cycle__year=today.year,
                plan__cycle__month=today.month,
                status=MonthlyMenuSchedule.Status.PUBLISHED,
            )
            .prefetch_related('slots__items__ingredient')
            .select_related('plan__meal_category')
            .first()
        )

        periods_payload = []
        if schedule and visible_periods:
            slot_map = {
                (slot.service_date, slot.meal_period): slot
                for slot in schedule.slots.all()
                if slot.service_date == today
            }
            for period in visible_periods:
                slot = slot_map.get((today, period))
                ingredients = []
                if slot is not None:
                    ingredients = [
                        {
                            'id': item.ingredient_id,
                            'name': item.ingredient.name,
                            'product_role': item.ingredient.product_role,
                        }
                        for item in slot.items.all()
                    ]
                periods_payload.append(
                    {
                        'meal_period': period,
                        'ingredients': ingredients,
                    }
                )

        packages.append(
            {
                'meal_category_id': order.meal_id,
                'meal_name': order.meal.meal_name,
                'order_id': order.id,
                'service_date': today.isoformat(),
                'periods': periods_payload,
                'schedule_published': schedule is not None,
            }
        )

    return {
        'service_date': today.isoformat(),
        'timezone': settings_obj.timezone,
        'lunch_reveal_time': settings_obj.lunch_reveal_time.strftime('%H:%M'),
        'dinner_reveal_time': settings_obj.dinner_reveal_time.strftime('%H:%M'),
        'visible_periods': visible_periods,
        'packages': packages,
    }
