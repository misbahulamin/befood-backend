from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from math import ceil, floor

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from meals.models import (
    Ingredient,
    MealCyclePlan,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from meals.services.plan_roles import MAIN_ROLE, plan_ingredient_role_map


MEAL_PERIODS = (
    MonthlyMenuSlot.MealPeriod.LUNCH,
    MonthlyMenuSlot.MealPeriod.DINNER,
)


def expected_slot_keys(year: int, month: int) -> list[tuple[date, str]]:
    days = calendar.monthrange(year, month)[1]
    keys: list[tuple[date, str]] = []
    for day in range(1, days + 1):
        service_date = date(year, month, day)
        for period in MEAL_PERIODS:
            keys.append((service_date, period))
    return keys


def _plan_quota_map(plan: MealCyclePlan) -> dict[int, int]:
    return {line.ingredient_id: line.servings_count for line in plan.lines.all()}


def build_quota_summary(schedule: MonthlyMenuSchedule) -> list[dict]:
    plan = schedule.plan
    quotas = _plan_quota_map(plan)
    roles = plan_ingredient_role_map(plan)
    usage_total: dict[int, int] = defaultdict(int)
    usage_lunch: dict[int, int] = defaultdict(int)
    usage_dinner: dict[int, int] = defaultdict(int)

    items = (
        MonthlyMenuSlotItem.objects.filter(slot__schedule=schedule)
        .select_related('slot', 'ingredient')
        .all()
    )
    for item in items:
        iid = item.ingredient_id
        usage_total[iid] += 1
        if item.slot.meal_period == MonthlyMenuSlot.MealPeriod.LUNCH:
            usage_lunch[iid] += 1
        else:
            usage_dinner[iid] += 1

    ingredient_ids = set(quotas.keys()) | set(usage_total.keys())
    ingredients = {
        ing.id: ing
        for ing in Ingredient.objects.filter(id__in=ingredient_ids).only('id', 'name')
    }

    summary = []
    for iid in sorted(ingredient_ids, key=lambda x: ingredients.get(x).name if ingredients.get(x) else str(x)):
        ing = ingredients.get(iid)
        planned = quotas.get(iid, 0)
        used = usage_total.get(iid, 0)
        summary.append(
            {
                'ingredient_id': iid,
                'ingredient_name': ing.name if ing else None,
                'product_role': roles.get(iid),
                'planned': planned,
                'used': used,
                'remaining': max(planned - used, 0),
                'lunch_count': usage_lunch.get(iid, 0),
                'dinner_count': usage_dinner.get(iid, 0),
                'over_quota': used > planned,
            }
        )
    return summary


def serialize_schedule_assignments(
    schedule: MonthlyMenuSchedule,
    *,
    customer_visible_only: bool = False,
) -> list[dict]:
    roles = plan_ingredient_role_map(schedule.plan)
    slots = (
        schedule.slots.prefetch_related('items__ingredient')
        .order_by('service_date', 'meal_period')
        .all()
    )
    result = []
    for slot in slots:
        ingredients = []
        for item in slot.items.all():
            if customer_visible_only and not item.ingredient.is_customer_visible:
                continue
            ingredients.append(
                {
                    'id': item.ingredient_id,
                    'name': item.ingredient.name,
                    'product_role': roles.get(item.ingredient_id),
                }
            )
        result.append(
            {
                'service_date': slot.service_date.isoformat(),
                'meal_period': slot.meal_period,
                'ingredients': ingredients,
            }
        )
    return result


def _validate_assignment_matrix(
    plan: MealCyclePlan,
    assignments: list[dict],
) -> list[dict]:
    """
    Normalize and validate bulk assignments.

    Each assignment: {service_date: date, meal_period: str, ingredient_ids: list[int]}
    """
    cycle = plan.cycle
    allowed_dates = {
        date(cycle.year, cycle.month, day)
        for day in range(1, calendar.monthrange(cycle.year, cycle.month)[1] + 1)
    }
    quotas = _plan_quota_map(plan)
    if not quotas:
        raise ValidationError({'assignments': 'Linked cycle plan has no ingredient lines.'})

    normalized: dict[tuple[date, str], list[int]] = {}
    for entry in assignments:
        service_date = entry['service_date']
        if isinstance(service_date, str):
            service_date = date.fromisoformat(service_date)
        meal_period = entry['meal_period']
        if meal_period not in MEAL_PERIODS:
            raise ValidationError(
                {'meal_period': f'Invalid meal_period "{meal_period}". Use lunch or dinner.'}
            )
        if service_date not in allowed_dates:
            raise ValidationError(
                {
                    'service_date': (
                        f'Date {service_date.isoformat()} is outside cycle '
                        f'{cycle.year}-{cycle.month:02d}.'
                    )
                }
            )
        ingredient_ids = list(entry.get('ingredient_ids') or [])
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise ValidationError(
                {
                    'ingredient_ids': (
                        f'Duplicate ingredients on {service_date.isoformat()} {meal_period}.'
                    )
                }
            )
        key = (service_date, meal_period)
        if key in normalized:
            raise ValidationError(
                {
                    'assignments': (
                        f'Duplicate slot {service_date.isoformat()} {meal_period} in payload.'
                    )
                }
            )
        normalized[key] = ingredient_ids

    all_ids = {iid for ids in normalized.values() for iid in ids}
    unknown = all_ids - set(quotas.keys())
    if unknown:
        raise ValidationError(
            {
                'ingredient_ids': (
                    f'Ingredients not on the linked cycle plan: {sorted(unknown)}.'
                )
            }
        )

    roles = plan_ingredient_role_map(plan)
    usage: dict[int, int] = defaultdict(int)

    for (service_date, meal_period), ingredient_ids in normalized.items():
        mains = [iid for iid in ingredient_ids if roles.get(iid) == MAIN_ROLE]
        if len(mains) > 1:
            raise ValidationError(
                {
                    'assignments': (
                        f'Slot {service_date.isoformat()} {meal_period} has more than one main '
                        f'ingredient.'
                    )
                }
            )
        for iid in ingredient_ids:
            usage[iid] += 1

    for iid, used in usage.items():
        planned = quotas.get(iid, 0)
        if used > planned:
            raise ValidationError(
                {
                    'quota': (
                        f'Ingredient {iid} used {used} times but plan allows {planned} '
                        f'(remaining would be {planned - used}).'
                    )
                }
            )

    return [
        {
            'service_date': service_date,
            'meal_period': meal_period,
            'ingredient_ids': ingredient_ids,
        }
        for (service_date, meal_period), ingredient_ids in sorted(
            normalized.items(), key=lambda x: (x[0][0], x[0][1])
        )
    ]


@transaction.atomic
def create_schedule_for_plan(plan: MealCyclePlan, notes: str = '') -> MonthlyMenuSchedule:
    plan = MealCyclePlan.objects.select_related('cycle').prefetch_related('lines').get(pk=plan.pk)
    if not plan.is_finalized:
        raise ValidationError(
            {'plan': 'Monthly menu schedule requires a finalized cycle plan.'}
        )
    if MonthlyMenuSchedule.objects.filter(plan_id=plan.pk).exists():
        raise ValidationError({'plan': 'This cycle plan already has a monthly menu schedule.'})
    return MonthlyMenuSchedule.objects.create(
        plan=plan,
        status=MonthlyMenuSchedule.Status.DRAFT,
        notes=notes or '',
    )


@transaction.atomic
def replace_schedule_assignments(
    schedule: MonthlyMenuSchedule,
    assignments: list[dict],
) -> MonthlyMenuSchedule:
    schedule = (
        MonthlyMenuSchedule.objects.select_for_update()
        .select_related('plan__cycle')
        .prefetch_related('plan__lines')
        .get(pk=schedule.pk)
    )
    if schedule.is_published:
        raise ValidationError(
            {'status': 'Published schedules cannot be edited. Unpublish first.'}
        )

    normalized = _validate_assignment_matrix(schedule.plan, assignments)
    schedule.slots.all().delete()

    for entry in normalized:
        if not entry['ingredient_ids']:
            continue
        slot = MonthlyMenuSlot.objects.create(
            schedule=schedule,
            service_date=entry['service_date'],
            meal_period=entry['meal_period'],
        )
        MonthlyMenuSlotItem.objects.bulk_create(
            [
                MonthlyMenuSlotItem(slot=slot, ingredient_id=iid)
                for iid in entry['ingredient_ids']
            ]
        )
    return schedule


def find_incomplete_main_slots(schedule: MonthlyMenuSchedule) -> list[dict]:
    cycle = schedule.plan.cycle
    expected = expected_slot_keys(cycle.year, cycle.month)
    roles = plan_ingredient_role_map(schedule.plan)
    slots = {
        (slot.service_date, slot.meal_period): slot
        for slot in schedule.slots.prefetch_related('items__ingredient').all()
    }
    incomplete = []
    for service_date, meal_period in expected:
        slot = slots.get((service_date, meal_period))
        if slot is None:
            incomplete.append(
                {
                    'service_date': service_date.isoformat(),
                    'meal_period': meal_period,
                    'reason': 'missing_slot',
                }
            )
            continue
        mains = [
            item
            for item in slot.items.all()
            if roles.get(item.ingredient_id) == MAIN_ROLE
        ]
        if len(mains) == 0:
            incomplete.append(
                {
                    'service_date': service_date.isoformat(),
                    'meal_period': meal_period,
                    'reason': 'missing_main',
                }
            )
        elif len(mains) > 1:
            incomplete.append(
                {
                    'service_date': service_date.isoformat(),
                    'meal_period': meal_period,
                    'reason': 'multiple_mains',
                }
            )
    return incomplete


@transaction.atomic
def publish_schedule(schedule: MonthlyMenuSchedule) -> MonthlyMenuSchedule:
    schedule = (
        MonthlyMenuSchedule.objects.select_for_update()
        .select_related('plan__cycle')
        .get(pk=schedule.pk)
    )
    if schedule.is_published:
        raise ValidationError({'status': 'Schedule is already published.'})

    incomplete = find_incomplete_main_slots(schedule)
    if incomplete:
        raise ValidationError(
            {
                'publish': 'Every date and meal period must have exactly one main ingredient.',
                'incomplete_slots': incomplete,
            }
        )

    # Quota integrity check (defensive)
    summary = build_quota_summary(schedule)
    over = [row for row in summary if row['over_quota']]
    if over:
        raise ValidationError({'quota': 'Schedule exceeds plan quotas.', 'details': over})

    schedule.status = MonthlyMenuSchedule.Status.PUBLISHED
    schedule.published_at = timezone.now()
    schedule.save(update_fields=['status', 'published_at', 'updated_at'])
    return schedule


@transaction.atomic
def unpublish_schedule(schedule: MonthlyMenuSchedule) -> MonthlyMenuSchedule:
    schedule = MonthlyMenuSchedule.objects.select_for_update().get(pk=schedule.pk)
    if not schedule.is_published:
        raise ValidationError({'status': 'Only published schedules can be unpublished.'})
    schedule.status = MonthlyMenuSchedule.Status.DRAFT
    schedule.published_at = None
    schedule.save(update_fields=['status', 'published_at', 'updated_at'])
    return schedule


def recommended_period_split(remaining: int) -> tuple[int, int]:
    """Odd remainder prefers lunch."""
    if remaining <= 0:
        return 0, 0
    lunch = ceil(remaining / 2)
    dinner = floor(remaining / 2)
    return lunch, dinner
