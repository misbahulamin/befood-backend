from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from user_management.models import (
    CustomerAddress,
    CustomerDeliveryPlace,
    CustomerProfile,
    MealDeliveryDayOverride,
    MealDeliveryPreference,
)
from user_management.services.delivery_place import DeliveryPlaceError, ensure_place_owned
from user_management.services.profile_completion import update_profile_completion

MEAL_TIMEZONE = ZoneInfo('Asia/Dhaka')


class DeliveryPreferenceError(Exception):
    def __init__(self, message, code='delivery_preference_error'):
        super().__init__(message)
        self.code = code


def get_or_create_preference(customer_profile) -> MealDeliveryPreference:
    pref, _ = MealDeliveryPreference.objects.get_or_create(customer_profile=customer_profile)
    return pref


def set_meal_delivery_preferences(
    customer_profile,
    *,
    lunch_place: CustomerDeliveryPlace | None = None,
    dinner_place: CustomerDeliveryPlace | None = None,
    clear_lunch: bool = False,
    clear_dinner: bool = False,
):
    """Update lunch/dinner defaults. Pass place objects or clear_* flags."""
    with transaction.atomic():
        pref = get_or_create_preference(customer_profile)
        if clear_lunch:
            pref.lunch_place = None
        elif lunch_place is not None:
            pref.lunch_place = ensure_place_owned(customer_profile, lunch_place)

        if clear_dinner:
            pref.dinner_place = None
        elif dinner_place is not None:
            pref.dinner_place = ensure_place_owned(customer_profile, dinner_place)

        pref.save()
        update_profile_completion(customer_profile)
    return pref


def replace_day_overrides(customer_profile, overrides: list[dict]):
    """
    Replace-set day overrides.

    Each item: {'meal_period': 'lunch'|'dinner', 'weekday': 0-6, 'place': CustomerDeliveryPlace}
    """
    seen = set()
    normalized = []
    for item in overrides:
        meal_period = item['meal_period']
        weekday = int(item['weekday'])
        place = item['place']
        if meal_period not in (
            MealDeliveryDayOverride.MealPeriod.LUNCH,
            MealDeliveryDayOverride.MealPeriod.DINNER,
        ):
            raise DeliveryPreferenceError('Invalid meal_period.', code='validation')
        if weekday < 0 or weekday > 6:
            raise DeliveryPreferenceError('weekday must be 0–6 (Monday=0).', code='validation')
        key = (meal_period, weekday)
        if key in seen:
            raise DeliveryPreferenceError(
                f'Duplicate override for {meal_period} weekday {weekday}.',
                code='validation',
            )
        seen.add(key)
        ensure_place_owned(customer_profile, place)
        normalized.append((meal_period, weekday, place))

    with transaction.atomic():
        MealDeliveryDayOverride.objects.filter(customer_profile=customer_profile).delete()
        MealDeliveryDayOverride.objects.bulk_create(
            [
                MealDeliveryDayOverride(
                    customer_profile=customer_profile,
                    meal_period=meal_period,
                    weekday=weekday,
                    place=place,
                )
                for meal_period, weekday, place in normalized
            ]
        )
        update_profile_completion(customer_profile)

    return list(
        MealDeliveryDayOverride.objects.filter(customer_profile=customer_profile)
        .select_related('place')
        .order_by('weekday', 'meal_period')
    )


def _iso_weekday_monday0(service_date: date) -> int:
    """Python date.weekday() is already Monday=0 … Sunday=6."""
    return service_date.weekday()


def _fallback_place(customer_profile: CustomerProfile) -> CustomerDeliveryPlace | None:
    place = (
        CustomerDeliveryPlace.objects.filter(
            customer_profile=customer_profile,
            is_active=True,
        )
        .order_by('created_at')
        .first()
    )
    if place:
        return place

    # Transition fallback: mirror present default into an ephemeral resolve from address book
    # only if a place was never created — try creating from present default lazily.
    present = customer_profile.addresses.filter(
        address_type=CustomerAddress.AddressType.PRESENT,
        is_default_delivery=True,
    ).first()
    if present:
        from user_management.services.delivery_place import create_delivery_place

        try:
            place = create_delivery_place(
                customer_profile,
                label=present.area.strip() or 'Home',
                full_address=present.full_address,
                city=present.city,
                area=present.area,
                building_name=present.building_name,
                floor=present.floor,
                flat_number=present.flat_number,
                landmark=present.landmark,
                latitude=present.latitude,
                longitude=present.longitude,
            )
        except DeliveryPlaceError:
            return None
        set_meal_delivery_preferences(
            customer_profile,
            lunch_place=place,
            dinner_place=place,
        )
        return place
    return None


def resolve_delivery_address(
    customer_profile: CustomerProfile,
    service_date: date,
    meal_period: str,
) -> CustomerDeliveryPlace | None:
    """
    Resolve effective place: day override → period default → fallback.

    Weekday uses the calendar date (Asia/Dhaka service dates are date-only).
    """
    if meal_period not in ('lunch', 'dinner'):
        raise DeliveryPreferenceError('meal_period must be lunch or dinner.', code='validation')

    weekday = _iso_weekday_monday0(service_date)
    override = (
        MealDeliveryDayOverride.objects.filter(
            customer_profile=customer_profile,
            meal_period=meal_period,
            weekday=weekday,
            place__is_active=True,
        )
        .select_related('place')
        .first()
    )
    if override:
        return override.place

    pref = MealDeliveryPreference.objects.filter(customer_profile=customer_profile).first()
    if pref:
        default_place = pref.lunch_place if meal_period == 'lunch' else pref.dinner_place
        if default_place is not None and default_place.is_active:
            return default_place

    return _fallback_place(customer_profile)


def preview_delivery_addresses(
    customer_profile: CustomerProfile,
    start_date: date,
    end_date: date,
    meal_periods: tuple[str, ...] = ('lunch', 'dinner'),
) -> list[dict]:
    if end_date < start_date:
        raise DeliveryPreferenceError('to must be on or after from.', code='validation')
    if (end_date - start_date).days > 62:
        raise DeliveryPreferenceError('Preview range cannot exceed 62 days.', code='validation')

    results = []
    current = start_date
    while current <= end_date:
        for period in meal_periods:
            place = resolve_delivery_address(customer_profile, current, period)
            results.append(
                {
                    'service_date': current,
                    'meal_period': period,
                    'place': place,
                }
            )
        current += timedelta(days=1)
    return results


def today_in_meal_tz() -> date:
    return timezone.now().astimezone(MEAL_TIMEZONE).date()
