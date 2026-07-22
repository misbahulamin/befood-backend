from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import ceil, floor

from django.core.exceptions import ValidationError
from django.db import transaction

from meals.models import Ingredient, MonthlyMenuSchedule, MonthlyMenuSlot
from meals.services.menu_schedule import (
    MEAL_PERIODS,
    build_quota_summary,
    expected_slot_keys,
    replace_schedule_assignments,
    serialize_schedule_assignments,
)


def _slot_main_map(schedule: MonthlyMenuSchedule) -> dict[tuple[date, str], int | None]:
    result: dict[tuple[date, str], int | None] = {}
    for slot in schedule.slots.prefetch_related('items__ingredient').all():
        main_id = None
        for item in slot.items.all():
            if item.ingredient.product_role == Ingredient.ProductRole.MAIN:
                main_id = item.ingredient_id
                break
        result[(slot.service_date, slot.meal_period)] = main_id
    return result


def _slot_all_items_map(schedule: MonthlyMenuSchedule) -> dict[tuple[date, str], list[int]]:
    result: dict[tuple[date, str], list[int]] = defaultdict(list)
    for slot in schedule.slots.prefetch_related('items').all():
        result[(slot.service_date, slot.meal_period)] = [
            item.ingredient_id for item in slot.items.all()
        ]
    return result


def _plan_quotas(schedule: MonthlyMenuSchedule) -> dict[int, dict]:
    quotas = {}
    for line in schedule.plan.lines.select_related('ingredient').all():
        quotas[line.ingredient_id] = {
            'servings_count': line.servings_count,
            'product_role': line.ingredient.product_role,
            'name': line.ingredient.name,
        }
    return quotas


def _current_usage(schedule: MonthlyMenuSchedule) -> dict[int, int]:
    usage: dict[int, int] = defaultdict(int)
    for row in build_quota_summary(schedule):
        usage[row['ingredient_id']] = row['used']
    return usage


def build_divergence_warnings(
    schedules: list[MonthlyMenuSchedule],
) -> list[dict]:
    if len(schedules) < 2:
        return []
    cycle = schedules[0].plan.cycle
    keys = expected_slot_keys(cycle.year, cycle.month)
    main_maps = {s.id: _slot_main_map(s) for s in schedules}
    warnings = []
    for service_date, meal_period in keys:
        package_mains = {}
        for s in schedules:
            mid = main_maps[s.id].get((service_date, meal_period))
            if mid is not None:
                package_mains[s.plan.meal_category_id] = {
                    'schedule_id': s.id,
                    'meal_category_id': s.plan.meal_category_id,
                    'meal_category_name': s.plan.meal_category.meal_name,
                    'ingredient_id': mid,
                }
        unique_mains = {v['ingredient_id'] for v in package_mains.values()}
        if len(unique_mains) > 1:
            warnings.append(
                {
                    'service_date': service_date.isoformat(),
                    'meal_period': meal_period,
                    'packages': list(package_mains.values()),
                }
            )
    return warnings


def build_sync_suggestion(
    source: MonthlyMenuSchedule,
    target: MonthlyMenuSchedule,
) -> dict:
    if source.plan.cycle_id != target.plan.cycle_id:
        raise ValidationError({'cycle': 'Source and target schedules must share the same cycle.'})
    if source.pk == target.pk:
        raise ValidationError({'target': 'Source and target schedules must be different.'})

    cycle = target.plan.cycle
    keys = expected_slot_keys(cycle.year, cycle.month)
    source_items = _slot_all_items_map(source)
    source_mains = _slot_main_map(source)
    target_quotas = _plan_quotas(target)
    remaining = {
        iid: data['servings_count'] for iid, data in target_quotas.items()
    }
    # Start from empty proposal for target (full replace suggestion)
    proposed: dict[tuple[date, str], list[int]] = {key: [] for key in keys}
    period_counts = {
        iid: {'lunch': 0, 'dinner': 0} for iid in remaining
    }

    # Phase 1: mirror mains from source where quota allows
    for key in keys:
        main_id = source_mains.get(key)
        if main_id is None:
            continue
        if main_id not in remaining:
            continue
        if remaining[main_id] <= 0:
            continue
        proposed[key].append(main_id)
        remaining[main_id] -= 1
        period_counts[main_id][key[1]] += 1

    # Phase 2: fill empty mains with remaining main quotas (balance heuristic)
    main_ids = [
        iid
        for iid, data in target_quotas.items()
        if data['product_role'] == Ingredient.ProductRole.MAIN and remaining[iid] > 0
    ]
    # Precompute target lunch/dinner goals for each remaining main
    goals = {}
    for iid in main_ids:
        r = remaining[iid]
        lunch_goal, dinner_goal = ceil(r / 2), floor(r / 2)
        # Add already placed from mirror
        goals[iid] = {
            'lunch': period_counts[iid]['lunch'] + lunch_goal,
            'dinner': period_counts[iid]['dinner'] + dinner_goal,
        }

    empty_main_slots = [key for key in keys if not any(
        iid in target_quotas and target_quotas[iid]['product_role'] == Ingredient.ProductRole.MAIN
        for iid in proposed[key]
    )]

    for key in empty_main_slots:
        period = key[1]
        # Prefer ingredient that still needs this period and has remaining
        candidates = []
        for iid in main_ids:
            if remaining[iid] <= 0:
                continue
            deficit = goals[iid][period] - period_counts[iid][period]
            # Overlap score: does source use this ingredient on this slot?
            overlap = 1 if source_mains.get(key) == iid else 0
            candidates.append((deficit, overlap, remaining[iid], iid))
        if not candidates:
            continue
        candidates.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))
        chosen = candidates[0][3]
        proposed[key].append(chosen)
        remaining[chosen] -= 1
        period_counts[chosen][period] += 1

    # Phase 3: mirror non-mains from source where quota allows
    for key in keys:
        for iid in source_items.get(key, []):
            if iid not in target_quotas:
                continue
            if target_quotas[iid]['product_role'] == Ingredient.ProductRole.MAIN:
                continue
            if remaining.get(iid, 0) <= 0:
                continue
            if iid in proposed[key]:
                continue
            proposed[key].append(iid)
            remaining[iid] -= 1
            period_counts[iid][key[1]] += 1

    assignments = [
        {
            'service_date': service_date.isoformat(),
            'meal_period': meal_period,
            'ingredient_ids': proposed[(service_date, meal_period)],
        }
        for service_date, meal_period in keys
        if proposed[(service_date, meal_period)]
    ]

    unfilled_mains = [
        {
            'service_date': service_date.isoformat(),
            'meal_period': meal_period,
        }
        for service_date, meal_period in keys
        if not any(
            iid in target_quotas
            and target_quotas[iid]['product_role'] == Ingredient.ProductRole.MAIN
            for iid in proposed[(service_date, meal_period)]
        )
    ]

    remaining_quota = [
        {
            'ingredient_id': iid,
            'ingredient_name': data['name'],
            'product_role': data['product_role'],
            'remaining': remaining[iid],
            'planned': data['servings_count'],
        }
        for iid, data in target_quotas.items()
        if remaining[iid] > 0
    ]

    return {
        'source_schedule_id': source.id,
        'target_schedule_id': target.id,
        'assignments': assignments,
        'unfilled_main_slots': unfilled_mains,
        'remaining_quota': remaining_quota,
        'divergence_warnings': build_divergence_warnings([source, target]),
    }


@transaction.atomic
def apply_sync_suggestion(
    target: MonthlyMenuSchedule,
    source: MonthlyMenuSchedule | None = None,
    assignments: list[dict] | None = None,
) -> MonthlyMenuSchedule:
    """
    Apply either an explicit assignments payload or recompute from source and apply.
    """
    if target.is_published:
        raise ValidationError(
            {'status': 'Cannot apply sync to a published schedule. Unpublish first.'}
        )
    if assignments is None:
        if source is None:
            raise ValidationError(
                {'source_schedule_id': 'Provide source_schedule_id or assignments.'}
            )
        suggestion = build_sync_suggestion(source, target)
        assignments = suggestion['assignments']

    # Normalize ingredient_ids keys for replace_schedule_assignments
    normalized_payload = []
    for entry in assignments:
        normalized_payload.append(
            {
                'service_date': entry['service_date'],
                'meal_period': entry['meal_period'],
                'ingredient_ids': entry.get('ingredient_ids') or [],
            }
        )
    return replace_schedule_assignments(target, normalized_payload)


def sync_suggestion_response(source: MonthlyMenuSchedule, target: MonthlyMenuSchedule) -> dict:
    suggestion = build_sync_suggestion(source, target)
    suggestion['target_current_assignments'] = serialize_schedule_assignments(target)
    return suggestion
