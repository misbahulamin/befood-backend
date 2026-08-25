from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from meals.models import MealCycle, MonthlyMenuSchedule
from meals.services.menu_schedule import serialize_schedule_assignments
from meals.services.pricing import expected_servings, get_month_days
from orders.models import CustomerSubscription, Order


def resolve_target_year_month(
    *,
    year: int | str | None = None,
    month: int | str | None = None,
    reference_date=None,
) -> tuple[int, int]:
    """
    Resolve calendar year/month for package menu lookup.

    Both omitted → current local month.
    Both provided → validated integers (month 1–12).
    Only one provided → ValidationError (400 at API layer).
    """
    year_provided = year is not None and str(year).strip() != ''
    month_provided = month is not None and str(month).strip() != ''

    if year_provided != month_provided:
        raise ValidationError(
            {
                'year': ['Both year and month are required together.'],
                'month': ['Both year and month are required together.'],
            }
        )

    if not year_provided and not month_provided:
        today = reference_date or timezone.localdate()
        return today.year, today.month

    try:
        year_int = int(year)
        month_int = int(month)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            {
                'year': ['Enter a valid year integer.'],
                'month': ['Enter a valid month integer (1–12).'],
            }
        ) from exc

    if month_int < 1 or month_int > 12:
        raise ValidationError({'month': ['Month must be between 1 and 12.']})
    if year_int < 1:
        raise ValidationError({'year': ['Enter a valid year.']})

    return year_int, month_int


def orders_for_customer_month(customer_profile, year: int, month: int):
    """Historical monthly orders (read-only). Prefer active subscription for live menus."""
    order_month = f'{year:04d}-{month:02d}'
    return (
        Order.objects.filter(
            customer=customer_profile,
            order_month=order_month,
        )
        .exclude(order_status=Order.OrderStatus.CANCELLED)
        .select_related('meal')
        .order_by('-created_at')
    )


def active_subscription_for_customer(customer_profile):
    return (
        CustomerSubscription.objects.filter(
            customer=customer_profile,
            status=CustomerSubscription.Status.ACTIVE,
        )
        .select_related('meal')
        .first()
    )


def build_menu_meta(meal, year: int, month: int) -> dict:
    """
    Package metadata for calendar/list UIs (duration, meal option).

    cycle_days comes from MealCycle when present, otherwise calendar month length.
    total_meals is package-scoped expected servings (service days × periods per day).
    """
    cycle = MealCycle.objects.filter(year=year, month=month).first()
    cycle_days = cycle.cycle_days if cycle is not None else get_month_days(year, month)
    total_meals = expected_servings(meal.meal_type, meal.meal_period, year, month)
    return {
        'cycle_days': cycle_days,
        'total_meals': total_meals,
        'meal_period': meal.meal_period,
        'meal_period_display': meal.get_meal_period_display(),
    }


def published_schedule_for_meal(meal_id: int, year: int, month: int):
    return (
        MonthlyMenuSchedule.objects.filter(
            plan__meal_category_id=meal_id,
            plan__cycle__year=year,
            plan__cycle__month=month,
            status=MonthlyMenuSchedule.Status.PUBLISHED,
        )
        .prefetch_related('slots__items__ingredient', 'plan__lines')
        .select_related('plan__meal_category', 'plan')
        .first()
    )


def build_package_menu_for_customer(
    customer_profile,
    *,
    year: int | str | None = None,
    month: int | str | None = None,
    reference_date=None,
) -> dict:
    target_year, target_month = resolve_target_year_month(
        year=year,
        month=month,
        reference_date=reference_date,
    )
    subscription = active_subscription_for_customer(customer_profile)
    packages = []
    if subscription is not None:
        schedule = published_schedule_for_meal(
            subscription.meal_id, target_year, target_month
        )
        days = (
            serialize_schedule_assignments(schedule, customer_visible_only=True)
            if schedule is not None
            else []
        )
        packages.append(
            {
                'meal_public_id': str(subscription.meal.public_id),
                'meal_name': subscription.meal.meal_name,
                'subscription_public_id': str(subscription.public_id),
                'order_public_id': None,
                'schedule_published': schedule is not None,
                'meta': build_menu_meta(subscription.meal, target_year, target_month),
                'days': days,
            }
        )

    return {
        'year': target_year,
        'month': target_month,
        'packages': packages,
    }


def build_order_menu_preview_for_meal(
    meal,
    *,
    year: int | str | None = None,
    month: int | str | None = None,
    reference_date=None,
) -> dict:
    """
    Pre-order published menu preview for a meal + month.

    Does not require the customer to own an order. Unpublished months return
    schedule_published=false with an empty day list.
    """
    target_year, target_month = resolve_target_year_month(
        year=year,
        month=month,
        reference_date=reference_date,
    )
    schedule = published_schedule_for_meal(meal.id, target_year, target_month)
    days = (
        serialize_schedule_assignments(schedule, customer_visible_only=True)
        if schedule is not None
        else []
    )
    return {
        'year': target_year,
        'month': target_month,
        'meal_public_id': str(meal.public_id),
        'meal_name': meal.meal_name,
        'schedule_published': schedule is not None,
        'meta': build_menu_meta(meal, target_year, target_month),
        'days': days,
    }


def build_public_package_menu_for_meal(
    meal,
    *,
    year: int | str | None = None,
    month: int | str | None = None,
    reference_date=None,
) -> dict:
    """
    Unauthenticated marketing-page menu read.

    Returns only published schedule slots; no customer/order/subscription data.
    """
    target_year, target_month = resolve_target_year_month(
        year=year,
        month=month,
        reference_date=reference_date,
    )
    schedule = published_schedule_for_meal(meal.id, target_year, target_month)
    days = (
        serialize_schedule_assignments(schedule, customer_visible_only=True)
        if schedule is not None
        else []
    )
    return {
        'year': target_year,
        'month': target_month,
        'meal_public_id': str(meal.public_id),
        'meal_name': meal.meal_name,
        'schedule_published': schedule is not None,
        'meta': build_menu_meta(meal, target_year, target_month),
        'days': days,
    }
