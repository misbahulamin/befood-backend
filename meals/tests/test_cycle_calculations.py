from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from meals.models import Ingredient, MealCategory, MealCycle, MealCyclePlan, MealCyclePlanLine
from meals.services.cycle_calculations import (
    build_plan_summary,
    calculate_package_totals,
    finalize_plan,
    resolve_cost_per_customer,
)
from meals.services.pricing import get_month_days, total_meals_for_month


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


class CycleCostingFormulaTests(TestCase):
    def setUp(self):
        self.beef = Ingredient.objects.create(
            name='Beef',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
            product_role=Ingredient.ProductRole.MAIN,
        )
        self.veg = Ingredient.objects.create(
            name='Vegetables',
            cost_per_customer=Decimal('6.00'),
            product_role=Ingredient.ProductRole.STAPLE,
        )

    def test_kg_cost_per_customer(self):
        cost = resolve_cost_per_customer(self.beef)
        self.assertEqual(cost, Decimal('54.166667'))

    def test_flat_cost_per_customer(self):
        self.assertEqual(resolve_cost_per_customer(self.veg), Decimal('6.000000'))

    def test_package_totals_april_style(self):
        # product_cost 2954.62, other 30%, profit 20%, / 60 meals
        totals = calculate_package_totals(
            product_cost=Decimal('2954.62'),
            other_cost_percent=Decimal('30'),
            profit_percent=Decimal('20'),
            expected_servings_count=60,
        )
        self.assertEqual(totals['other_cost'], Decimal('886.39'))
        self.assertEqual(totals['profit'], Decimal('590.92'))
        self.assertEqual(totals['total_cost'], Decimal('4431.93'))
        self.assertEqual(totals['per_meal_rate'], Decimal('73.87'))

    def test_package_totals_january_uses_62_meals(self):
        totals = calculate_package_totals(
            product_cost=Decimal('2954.62'),
            other_cost_percent=Decimal('30'),
            profit_percent=Decimal('20'),
            expected_servings_count=62,
        )
        self.assertEqual(totals['per_meal_rate'], Decimal('71.48'))

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
            other_cost_percent=Decimal('30'),
            profit_percent=Decimal('20'),
        )
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.beef, servings_count=2)
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
            other_cost_percent=Decimal('30'),
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.beef, servings_count=60)
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.veg, servings_count=60)
        finalize_plan(plan)
        plan.refresh_from_db()
        summary = build_plan_summary(plan)
        self.assertTrue(summary['using_snapshot'])
        self.assertEqual(plan.status, MealCyclePlan.Status.FINALIZED)
        self.assertIsNotNone(plan.snapshot_per_meal_rate)
        self.assertEqual(summary['expected_servings'], 60)
        self.assertEqual(summary['main_servings_expected'], 60)

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
            other_cost_percent=Decimal('30'),
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.beef, servings_count=30)
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
            other_cost_percent=Decimal('30'),
            profit_percent=Decimal('10'),
        )
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.beef, servings_count=2)
        finalize_plan(plan)
        plan.refresh_from_db()
        summary = build_plan_summary(plan)
        self.assertEqual(summary['expected_servings'], 2)
        # per_meal_rate = total_cost / 2
        product = Decimal(summary['product_cost'])
        other = Decimal(summary['other_cost'])
        profit = Decimal(summary['profit'])
        total = product + other + profit
        self.assertEqual(Decimal(summary['per_meal_rate']), (total / Decimal('2')).quantize(Decimal('0.01')))
