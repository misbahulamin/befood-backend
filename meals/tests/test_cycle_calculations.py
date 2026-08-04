from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from meals.models import Ingredient, MealCategory, MealCycle, MealCyclePlan, MealCyclePlanLine
from meals.services.cycle_calculations import (
    build_line_detail,
    build_plan_summary,
    calculate_line_product_cost,
    calculate_package_totals,
    combined_unit_cost_per_customer,
    finalize_plan,
    resolved_kg_cost_per_customer,
    resolve_cost_per_customer,
)
from meals.services.operational_cost import (
    per_meal_operational_cost_for_month,
    resolve_per_meal_operational_cost,
    total_operational_cost,
)
from meals.services.pricing import get_month_days, total_meals_for_month
from meals.tests.helpers import ensure_operational_cost_month


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class MonthMealCountTests(SimpleTestCase):
    def test_january_has_62_meals(self):
        self.assertEqual(get_month_days(2026, 1), 31)
        self.assertEqual(total_meals_for_month(2026, 1), 62)

    def test_april_has_60_meals(self):
        self.assertEqual(get_month_days(2026, 4), 30)
        self.assertEqual(total_meals_for_month(2026, 4), 60)


class OperationalCostServiceTests(TestCase):
    def test_july_example_per_meal_cost(self):
        month = ensure_operational_cost_month(
            2026,
            7,
            target_meal_quantity=10_000,
            items=[
                ('Office Rent', Decimal('50000.00')),
                ('Electricity', Decimal('10000.00')),
                ('Employee Salary', Decimal('200000.00')),
                ('Chef Salary', Decimal('50000.00')),
            ],
        )
        self.assertEqual(total_operational_cost(month), Decimal('310000.00'))
        self.assertEqual(per_meal_operational_cost_for_month(month), Decimal('31.00'))
        self.assertEqual(resolve_per_meal_operational_cost(2026, 7), Decimal('31.00'))

    def test_empty_ledger_zero_per_meal(self):
        month = ensure_operational_cost_month(2026, 9, target_meal_quantity=10_000, items=[])
        self.assertEqual(total_operational_cost(month), Decimal('0.00'))
        self.assertEqual(per_meal_operational_cost_for_month(month), Decimal('0.00'))

    def test_resolve_missing_month_fails(self):
        with self.assertRaises(ValidationError) as ctx:
            resolve_per_meal_operational_cost(2026, 11)
        self.assertIn('operational_cost_month', ctx.exception.message_dict)


class CycleCostingFormulaTests(TestCase):
    def setUp(self):
        self.beef = Ingredient.objects.create(
            name='Beef',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
        )
        self.veg = Ingredient.objects.create(
            name='Vegetables',
            cost_per_customer=Decimal('6.00'),
        )
        ensure_operational_cost_month(2026, 4, items=[])
        ensure_operational_cost_month(2026, 8, items=[])

    def test_kg_cost_per_customer(self):
        cost = resolve_cost_per_customer(self.beef)
        self.assertEqual(cost, Decimal('54.166667'))
        self.assertEqual(resolved_kg_cost_per_customer(self.beef), Decimal('54.166667'))

    def test_flat_only_has_no_kg_resolved_cost(self):
        self.assertIsNone(resolved_kg_cost_per_customer(self.veg))
        self.assertEqual(combined_unit_cost_per_customer(self.veg), Decimal('6.000000'))

    def test_resolve_cost_rejects_ingredient_without_kg(self):
        with self.assertRaises(ValidationError) as ctx:
            resolve_cost_per_customer(self.veg)
        self.assertIn('ingredient', ctx.exception.message_dict)
        unpriced = Ingredient.objects.create(name='Unpriced')
        with self.assertRaises(ValidationError) as ctx:
            resolve_cost_per_customer(unpriced)
        self.assertIn('ingredient', ctx.exception.message_dict)

    def test_kg_only_line_product_cost(self):
        meal = MealCategory.objects.create(
            meal_name='Kg Only Plan',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('kg-only.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=5)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=meal)
        line = MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=2,
        )
        detail = build_line_detail(line)
        expected = calculate_line_product_cost(Decimal('54.166667'), 2)
        self.assertEqual(detail['resolved_cost_per_customer'], '54.166667')
        self.assertIsNone(detail['cost_per_customer'])
        self.assertEqual(detail['line_product_cost'], str(expected))

    def test_flat_only_line_product_cost(self):
        meal = MealCategory.objects.create(
            meal_name='Flat Only Plan',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('flat-only.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=6)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=meal)
        line = MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.veg,
            product_role=MealCyclePlanLine.ProductRole.STAPLE,
            servings_count=60,
        )
        detail = build_line_detail(line)
        self.assertIsNone(detail['resolved_cost_per_customer'])
        self.assertEqual(detail['cost_per_customer'], '6.000000')
        self.assertEqual(detail['line_product_cost'], '360.00')

    def test_additive_kg_plus_flat_line_product_cost(self):
        both = Ingredient.objects.create(
            name='Chicken Both',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
            cost_per_customer=Decimal('2.00'),
        )
        self.assertEqual(combined_unit_cost_per_customer(both), Decimal('56.166667'))
        meal = MealCategory.objects.create(
            meal_name='Additive Plan',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('additive.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=7)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=meal)
        line = MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=both,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=10,
        )
        detail = build_line_detail(line)
        expected = calculate_line_product_cost(Decimal('56.166667'), 10)
        self.assertEqual(detail['resolved_cost_per_customer'], '54.166667')
        self.assertEqual(detail['cost_per_customer'], '2.000000')
        self.assertEqual(detail['line_product_cost'], str(expected))

    def test_summary_rejects_unpriced_line_ingredient(self):
        unpriced = Ingredient.objects.create(name='Unpriced Line')
        meal = MealCategory.objects.create(
            meal_name='Unpriced Plan',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('unpriced-plan.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=4)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=unpriced,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=60,
        )
        with self.assertRaises(ValidationError) as ctx:
            build_plan_summary(plan)
        self.assertIn('ingredient', ctx.exception.message_dict)

    def test_summary_rejects_missing_operational_month(self):
        meal = MealCategory.objects.create(
            meal_name='No Op Cost',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('no-op.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=12)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=meal)
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=62,
        )
        with self.assertRaises(ValidationError) as ctx:
            build_plan_summary(plan)
        self.assertIn('operational_cost_month', ctx.exception.message_dict)

    def test_package_totals_uses_per_meal_operational_cost(self):
        totals = calculate_package_totals(
            product_cost=Decimal('2954.62'),
            per_meal_operational_cost=Decimal('31.00'),
            profit_percent=Decimal('20'),
            expected_servings_count=60,
        )
        self.assertEqual(totals['other_cost'], Decimal('1860.00'))
        self.assertEqual(totals['profit'], Decimal('590.92'))
        self.assertEqual(totals['total_cost'], Decimal('5405.54'))
        self.assertEqual(totals['per_meal_rate'], Decimal('90.09'))
        self.assertEqual(totals['per_meal_operational_cost'], Decimal('31.00'))

    def test_package_totals_january_uses_62_meals(self):
        totals = calculate_package_totals(
            product_cost=Decimal('2954.62'),
            per_meal_operational_cost=Decimal('31.00'),
            profit_percent=Decimal('20'),
            expected_servings_count=62,
        )
        self.assertEqual(totals['other_cost'], Decimal('1922.00'))
        self.assertEqual(totals['per_meal_rate'], Decimal('88.19'))

    def test_other_cost_independent_of_product_cost(self):
        totals = calculate_package_totals(
            product_cost=Decimal('100.00'),
            per_meal_operational_cost=Decimal('31.00'),
            profit_percent=Decimal('10'),
            expected_servings_count=10_000,
        )
        self.assertEqual(totals['other_cost'], Decimal('310000.00'))

    def test_finalize_requires_main_servings_match(self):
        meal = MealCategory.objects.create(
            meal_name='Plan A',
            total_price=Decimal('3000.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('a.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=4)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('20'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=2,
        )
        with self.assertRaises(ValidationError):
            finalize_plan(plan)

    def test_finalize_snapshot_summary(self):
        meal = MealCategory.objects.create(
            meal_name='Plan B',
            total_price=Decimal('3000.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('b.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=4)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=60,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.veg,
            product_role=MealCyclePlanLine.ProductRole.STAPLE,
            servings_count=60,
        )
        finalize_plan(plan)
        plan.refresh_from_db()
        summary = build_plan_summary(plan)
        self.assertTrue(summary['using_snapshot'])
        self.assertEqual(plan.status, MealCyclePlan.Status.FINALIZED)
        self.assertIsNotNone(plan.snapshot_per_meal_rate)
        self.assertEqual(summary['expected_servings'], 60)
        self.assertEqual(summary['main_servings_expected'], 60)
        self.assertEqual(plan.snapshot_other_cost, Decimal('0.00'))

    def test_finalize_with_july_operational_allocation(self):
        ensure_operational_cost_month(
            2026,
            7,
            target_meal_quantity=10_000,
            items=[
                ('Office Rent', Decimal('50000.00')),
                ('Electricity', Decimal('10000.00')),
                ('Employee Salary', Decimal('200000.00')),
                ('Chef Salary', Decimal('50000.00')),
            ],
        )
        meal = MealCategory.objects.create(
            meal_name='July Plan',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('july.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=7)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=62,
        )
        finalize_plan(plan)
        plan.refresh_from_db()
        self.assertEqual(plan.snapshot_other_cost, Decimal('1922.00'))  # 62 × 31
        summary = build_plan_summary(plan)
        self.assertEqual(summary['per_meal_operational_cost'], '31.00')

    def test_finalize_monthly_dinner_expects_30_in_april(self):
        meal = MealCategory.objects.create(
            meal_name='Dinner Only',
            total_price=None,
            meal_type='monthly',
            meal_period='dinner',
            meal_thumbnail=make_test_image('dinner.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=4)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=30,
        )
        finalize_plan(plan)
        plan.refresh_from_db()
        summary = build_plan_summary(plan)
        self.assertEqual(summary['expected_servings'], 30)
        self.assertEqual(summary['per_meal_rate'], str(plan.snapshot_per_meal_rate))

    def test_finalize_daily_both_expects_2(self):
        meal = MealCategory.objects.create(
            meal_name='Daily Both',
            total_price=None,
            meal_type='daily',
            meal_period='both',
            meal_thumbnail=make_test_image('daily-both.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=4)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=2,
        )
        finalize_plan(plan)
        plan.refresh_from_db()
        summary = build_plan_summary(plan)
        self.assertEqual(summary['expected_servings'], 2)
        product = Decimal(summary['product_cost'])
        other = Decimal(summary['other_cost'])
        profit = Decimal(summary['profit'])
        total = product + other + profit
        self.assertEqual(
            Decimal(summary['per_meal_rate']),
            (total / Decimal('2')).quantize(Decimal('0.01')),
        )

    def test_summary_product_cost_sums_additive_line_costs(self):
        both = Ingredient.objects.create(
            name='Beef Plus Cooking',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
            cost_per_customer=Decimal('2.00'),
        )
        meal = MealCategory.objects.create(
            meal_name='Sum Additive',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('sum-additive.jpg'),
        )
        cycle = MealCycle.objects.create(year=2026, month=8)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=meal,
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=both,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=10,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.veg,
            product_role=MealCyclePlanLine.ProductRole.STAPLE,
            servings_count=60,
        )
        summary = build_plan_summary(plan)
        line_sum = sum(
            (Decimal(item['line_product_cost']) for item in summary['lines']),
            Decimal('0.00'),
        )
        self.assertEqual(Decimal(summary['product_cost']), line_sum)
        expected_both = calculate_line_product_cost(Decimal('56.166667'), 10)
        expected_veg = calculate_line_product_cost(Decimal('6.000000'), 60)
        self.assertEqual(line_sum, expected_both + expected_veg)
