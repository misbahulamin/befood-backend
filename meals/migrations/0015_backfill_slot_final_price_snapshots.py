# Data migration: backfill published slot final-price snapshots.

from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


MONEY = Decimal('0.01')
COST = Decimal('0.000001')


def _quantize(value, places=MONEY):
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _combined_unit_cost(ingredient):
    kg = Decimal('0')
    if ingredient.price_per_kg is not None and ingredient.customers_per_kg:
        kg = _quantize(
            Decimal(ingredient.price_per_kg) / Decimal(ingredient.customers_per_kg),
            COST,
        )
    flat = Decimal(ingredient.cost_per_customer or 0)
    return _quantize(kg + flat, COST)


def _has_cost(ingredient):
    has_kg = ingredient.price_per_kg is not None and ingredient.customers_per_kg is not None
    return has_kg or ingredient.cost_per_customer is not None


def backfill_slot_prices(apps, schema_editor):
    MonthlyMenuSchedule = apps.get_model('meals', 'MonthlyMenuSchedule')
    MonthlyMenuSlot = apps.get_model('meals', 'MonthlyMenuSlot')
    OperationalCostMonth = apps.get_model('meals', 'OperationalCostMonth')
    OperationalCostItem = apps.get_model('meals', 'OperationalCostItem')

    published = MonthlyMenuSchedule.objects.filter(status='published').select_related(
        'plan__cycle',
        'plan',
    )
    for schedule in published.iterator():
        cycle = schedule.plan.cycle
        try:
            cost_month = OperationalCostMonth.objects.get(year=cycle.year, month=cycle.month)
        except OperationalCostMonth.DoesNotExist:
            continue
        if not cost_month.target_meal_quantity:
            continue
        total_op = sum(
            (Decimal(item.amount) for item in OperationalCostItem.objects.filter(month=cost_month)),
            Decimal('0'),
        )
        per_meal_op = _quantize(total_op / Decimal(cost_month.target_meal_quantity))
        profit_percent = Decimal(schedule.plan.profit_percent)

        slots = MonthlyMenuSlot.objects.filter(schedule_id=schedule.pk).prefetch_related(
            'items__ingredient'
        )
        for slot in slots:
            items = list(slot.items.all())
            if not items:
                continue
            ingredients = [item.ingredient for item in items]
            if any(not _has_cost(ing) for ing in ingredients):
                continue
            selected = sum((_combined_unit_cost(ing) for ing in ingredients), Decimal('0'))
            selected = _quantize(selected, COST)
            profit = _quantize(selected * (profit_percent / Decimal('100')))
            final_price = _quantize(selected + per_meal_op + profit)
            slot.final_meal_price_snapshot = final_price
            slot.ingredient_cost_snapshot = _quantize(selected)
            slot.operational_cost_snapshot = per_meal_op
            slot.profit_snapshot = profit
            slot.ingredient_cost_lines = [
                {
                    'name': ing.name,
                    'unit_cost_per_customer': str(_combined_unit_cost(ing)),
                }
                for ing in ingredients
            ]
            slot.save(
                update_fields=[
                    'final_meal_price_snapshot',
                    'ingredient_cost_snapshot',
                    'operational_cost_snapshot',
                    'profit_snapshot',
                    'ingredient_cost_lines',
                ]
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0014_meal_slot_final_price_snapshots'),
    ]

    operations = [
        migrations.RunPython(backfill_slot_prices, noop_reverse),
    ]
