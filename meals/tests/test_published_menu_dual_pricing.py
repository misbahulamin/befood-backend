"""Admin published-menu dual pricing (subscriber + Instant ladders)."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import (
    Ingredient,
    InstantMealSettings,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MealCyclePlanLine,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from meals.services.cycle_calculations import build_one_meal_price_preview, finalize_plan
from meals.services.instant_meals import update_instant_meal_settings
from meals.services.menu_schedule import (
    create_schedule_for_plan,
    expected_slot_keys,
    publish_schedule,
    replace_schedule_assignments,
    serialize_schedule_assignments,
)
from meals.services.pricing import calculate_meal_price
from meals.services.slot_pricing import resolve_published_slot_for_delivery
from meals.tests.helpers import ensure_operational_cost_month
from user_management.models import AdminProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class PublishedMenuDualPricingTests(TestCase):
    def setUp(self):
        # per_meal_op = 413 / 100 = 4.13
        ensure_operational_cost_month(
            2026,
            7,
            target_meal_quantity=100,
            items=[('Rent', Decimal('413.00'))],
        )
        InstantMealSettings.load()
        update_instant_meal_settings(profit_percent=Decimal('70.00'))

        self.meal = MealCategory.objects.create(
            meal_name='Fish Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('fish.jpg'),
        )
        self.fish = Ingredient.objects.create(
            name='Fish',
            cost_per_customer=Decimal('48.15'),
        )
        self.side = Ingredient.objects.create(
            name='Side',
            cost_per_customer=Decimal('0.00'),
        )
        self.cycle = MealCycle.objects.create(year=2026, month=7)
        self.plan = MealCyclePlan.objects.create(
            cycle=self.cycle,
            meal_category=self.meal,
            profit_percent=Decimal('14.45'),
        )
        total = self.cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.fish,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total,
        )
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.side,
            product_role=MealCyclePlanLine.ProductRole.SIDE,
            servings_count=total,
        )
        finalize_plan(self.plan)
        self.schedule = create_schedule_for_plan(self.plan)

    def _assign_and_publish(self):
        keys = expected_slot_keys(2026, 7)
        assignments = [
            {
                'service_date': service_date,
                'meal_period': period,
                'ingredient_ids': [self.fish.id, self.side.id],
            }
            for service_date, period in keys
        ]
        replace_schedule_assignments(self.schedule, assignments)
        publish_schedule(self.schedule)
        self.schedule.refresh_from_db()

    def test_serialize_dual_ladders_worked_example(self):
        self._assign_and_publish()
        lunch = (
            self.schedule.slots.filter(
                service_date=date(2026, 7, 1),
                meal_period='lunch',
            ).first()
        )
        self.assertIsNotNone(lunch)
        self.assertEqual(lunch.ingredient_cost_snapshot, Decimal('48.15'))
        self.assertEqual(lunch.operational_cost_snapshot, Decimal('4.13'))
        self.assertEqual(lunch.final_meal_price_snapshot, Decimal('59.24'))

        entries = serialize_schedule_assignments(self.schedule)
        lunch_entry = next(
            e
            for e in entries
            if e['service_date'] == '2026-07-01' and e['meal_period'] == 'lunch'
        )
        self.assertEqual(lunch_entry['final_meal_price'], '59.24')
        self.assertEqual(lunch_entry['selected_ingredients_cost'], '48.15')
        self.assertEqual(lunch_entry['operational_cost'], '4.13')
        self.assertEqual(
            lunch_entry['subscriber_pricing'],
            {
                'profit_percent': '14.45',
                'profit_amount': '6.96',
                'final_price': '59.24',
            },
        )
        self.assertEqual(
            lunch_entry['instant_pricing'],
            {
                'profit_percent': '70.00',
                'profit_amount': '33.71',
                'final_price': '85.99',
            },
        )
        self.assertEqual(lunch_entry['subscriber_price'], '59.24')
        self.assertEqual(lunch_entry['instant_price'], '85.99')

    def test_instant_percent_change_refreshes_instant_only(self):
        self._assign_and_publish()
        lunch = self.schedule.slots.filter(
            service_date=date(2026, 7, 1),
            meal_period='lunch',
        ).get()
        locked = lunch.final_meal_price_snapshot

        update_instant_meal_settings(profit_percent=Decimal('80.00'))
        lunch_entry = next(
            e
            for e in serialize_schedule_assignments(self.schedule)
            if e['service_date'] == '2026-07-01' and e['meal_period'] == 'lunch'
        )
        # 48.15 + 4.13 + 38.52 = 90.80
        expected = calculate_meal_price(
            Decimal('48.15'),
            Decimal('4.13'),
            Decimal('80.00'),
        )
        self.assertEqual(lunch_entry['instant_pricing']['final_price'], expected['final_price'])
        self.assertEqual(lunch_entry['instant_pricing']['profit_amount'], expected['profit_amount'])
        self.assertEqual(lunch_entry['subscriber_price'], '59.24')
        self.assertEqual(lunch_entry['final_meal_price'], '59.24')

        lunch.refresh_from_db()
        self.assertEqual(lunch.final_meal_price_snapshot, locked)

    def test_multi_slot_distinct_prices(self):
        self._assign_and_publish()
        dinner = self.schedule.slots.get(
            service_date=date(2026, 7, 1),
            meal_period='dinner',
        )
        # Override dinner snapshots to a cheaper meal for contrast.
        dinner.ingredient_cost_snapshot = Decimal('30.00')
        dinner.operational_cost_snapshot = Decimal('4.13')
        dinner.profit_snapshot = Decimal('4.33')  # 30 * 14.45%
        dinner.final_meal_price_snapshot = Decimal('38.46')
        dinner.save()

        entries = {
            (e['service_date'], e['meal_period']): e
            for e in serialize_schedule_assignments(self.schedule)
        }
        lunch = entries[('2026-07-01', 'lunch')]
        dinner_entry = entries[('2026-07-01', 'dinner')]
        self.assertNotEqual(lunch['subscriber_price'], dinner_entry['subscriber_price'])
        self.assertNotEqual(lunch['instant_price'], dinner_entry['instant_price'])
        self.assertEqual(dinner_entry['selected_ingredients_cost'], '30.00')
        self.assertEqual(dinner_entry['instant_pricing']['profit_percent'], '70.00')

    def test_draft_without_snapshots_has_null_dual_pricing(self):
        slot = MonthlyMenuSlot.objects.create(
            schedule=self.schedule,
            service_date=date(2026, 7, 1),
            meal_period='lunch',
        )
        MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=self.fish)
        entries = serialize_schedule_assignments(self.schedule)
        entry = next(
            e
            for e in entries
            if e['service_date'] == '2026-07-01' and e['meal_period'] == 'lunch'
        )
        self.assertIsNone(entry['final_meal_price'])
        self.assertIsNone(entry['selected_ingredients_cost'])
        self.assertIsNone(entry['instant_pricing'])
        self.assertIsNone(entry['subscriber_pricing'])

    def test_instant_settings_patch_does_not_mutate_snapshots(self):
        self._assign_and_publish()
        slot = self.schedule.slots.filter(meal_period='lunch').first()
        before = (
            slot.final_meal_price_snapshot,
            slot.ingredient_cost_snapshot,
            slot.operational_cost_snapshot,
            slot.profit_snapshot,
        )
        plan_profit = self.plan.profit_percent
        update_instant_meal_settings(profit_percent=Decimal('55.00'))
        slot.refresh_from_db()
        self.plan.refresh_from_db()
        self.assertEqual(
            (
                slot.final_meal_price_snapshot,
                slot.ingredient_cost_snapshot,
                slot.operational_cost_snapshot,
                slot.profit_snapshot,
            ),
            before,
        )
        self.assertEqual(self.plan.profit_percent, plan_profit)

    def test_wallet_charge_uses_subscriber_snapshot_not_instant(self):
        self._assign_and_publish()
        update_instant_meal_settings(profit_percent=Decimal('90.00'))
        slot = resolve_published_slot_for_delivery(
            meal_id=self.meal.id,
            service_date=date(2026, 7, 1),
            meal_period='lunch',
        )
        self.assertIsNotNone(slot)
        self.assertEqual(slot.final_meal_price_snapshot, Decimal('59.24'))
        lunch_entry = next(
            e
            for e in serialize_schedule_assignments(self.schedule)
            if e['service_date'] == '2026-07-01' and e['meal_period'] == 'lunch'
        )
        # Instant ladder moved with settings; subscriber charge basis did not.
        self.assertNotEqual(lunch_entry['instant_price'], '59.24')
        self.assertEqual(lunch_entry['final_meal_price'], '59.24')
        self.assertEqual(
            Decimal(lunch_entry['final_meal_price']),
            slot.final_meal_price_snapshot,
        )

    def test_cost_preview_matches_shared_helper(self):
        preview = build_one_meal_price_preview(
            [self.fish],
            per_meal_operational_cost=Decimal('4.13'),
            profit_percent=Decimal('14.45'),
        )
        expected = calculate_meal_price(
            Decimal('48.15'),
            Decimal('4.13'),
            Decimal('14.45'),
        )
        self.assertEqual(preview['selected_ingredients_cost'], expected['ingredient_cost'])
        self.assertEqual(preview['per_meal_operational_cost'], expected['operational_cost'])
        self.assertEqual(preview['profit'], expected['profit_amount'])
        self.assertEqual(preview['final_meal_price'], expected['final_price'])
        self.assertEqual(preview['profit_percent'], expected['profit_percent'])


@override_settings(MEDIA_ROOT='test_media')
class PublishedMenuDualPricingAPITests(APITestCase):
    def setUp(self):
        ensure_operational_cost_month(
            2026,
            7,
            target_meal_quantity=100,
            items=[('Rent', Decimal('413.00'))],
        )
        InstantMealSettings.load()
        update_instant_meal_settings(profit_percent=Decimal('70.00'))

        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='dual-price-admin',
            email='dual-price-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.meal = MealCategory.objects.create(
            meal_name='API Fish Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('api-fish.jpg'),
        )
        self.fish = Ingredient.objects.create(
            name='API Fish',
            cost_per_customer=Decimal('48.15'),
        )
        self.cycle = MealCycle.objects.create(year=2026, month=7)
        self.plan = MealCyclePlan.objects.create(
            cycle=self.cycle,
            meal_category=self.meal,
            profit_percent=Decimal('14.45'),
        )
        total = self.cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.fish,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total,
        )
        finalize_plan(self.plan)
        self.schedule = create_schedule_for_plan(self.plan)
        keys = expected_slot_keys(2026, 7)
        replace_schedule_assignments(
            self.schedule,
            [
                {
                    'service_date': service_date,
                    'meal_period': period,
                    'ingredient_ids': [self.fish.id],
                }
                for service_date, period in keys
            ],
        )
        publish_schedule(self.schedule)

    def test_admin_retrieve_includes_dual_pricing(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        url = reverse(
            'meals:menu-schedules-detail',
            kwargs={'public_id': self.schedule.public_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        lunch = next(
            a
            for a in response.data['assignments']
            if a['service_date'] == '2026-07-01' and a['meal_period'] == 'lunch'
        )
        self.assertEqual(lunch['final_meal_price'], '59.24')
        self.assertEqual(lunch['subscriber_pricing']['final_price'], '59.24')
        self.assertEqual(lunch['instant_pricing']['final_price'], '85.99')
        self.assertEqual(lunch['instant_price'], '85.99')
