"""Tests for per-slot final meal price snapshots and package menu isolation."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import (
    Ingredient,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MealCyclePlanLine,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from meals.services.cycle_calculations import finalize_plan
from meals.services.menu_schedule import (
    create_schedule_for_plan,
    expected_slot_keys,
    publish_schedule,
    replace_schedule_assignments,
    unpublish_schedule,
)
from meals.services.menu_sync import apply_sync_suggestion
from meals.services.slot_pricing import compute_slot_final_price
from meals.tests.helpers import ensure_operational_cost_month
from orders.models import OrderDelivery, OrderWalletSettings
from orders.services.meal_payment import MealPaymentError, charge_delivered_meal
from orders.services.order_delivery import mark_delivery
from orders.services.order_service import create_meal_order
from user_management.models import AdminProfile, CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class SlotFinalPriceServiceTests(TestCase):
    def setUp(self):
        ensure_operational_cost_month(
            2026,
            7,
            target_meal_quantity=100,
            items=[('Rent', Decimal('3100.00'))],
        )
        # per_meal_op = 3100/100 = 31.00
        self.meal = MealCategory.objects.create(
            meal_name='Premium Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('premium.jpg'),
        )
        self.chicken = Ingredient.objects.create(
            name='Chicken',
            cost_per_customer=Decimal('20.00'),
        )
        self.rice = Ingredient.objects.create(
            name='Rice',
            cost_per_customer=Decimal('8.00'),
        )
        self.dal = Ingredient.objects.create(
            name='Dal',
            cost_per_customer=Decimal('3.00'),
        )
        self.alu = Ingredient.objects.create(
            name='Alu Vorta',
            cost_per_customer=Decimal('4.00'),
        )
        self.cycle = MealCycle.objects.create(year=2026, month=7)
        self.plan = MealCyclePlan.objects.create(
            cycle=self.cycle,
            meal_category=self.meal,
            profit_percent=Decimal('10.00'),
        )
        total = self.cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total // 2,
        )
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.alu,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total - (total // 2),
        )
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.rice,
            product_role=MealCyclePlanLine.ProductRole.SIDE,
            servings_count=total,
        )
        MealCyclePlanLine.objects.create(
            plan=self.plan,
            ingredient=self.dal,
            product_role=MealCyclePlanLine.ProductRole.SIDE,
            servings_count=total // 2,
        )
        finalize_plan(self.plan)
        self.schedule = create_schedule_for_plan(self.plan)

    def _full_assignments(self):
        keys = expected_slot_keys(2026, 7)
        half = len(keys) // 2
        assignments = []
        for index, (service_date, meal_period) in enumerate(keys):
            if index < half:
                ids = [self.chicken.id, self.rice.id, self.dal.id]
            else:
                ids = [self.alu.id, self.rice.id]
            assignments.append(
                {
                    'service_date': service_date,
                    'meal_period': meal_period,
                    'ingredient_ids': ids,
                }
            )
        return assignments

    def test_lunch_and_dinner_prices_differ(self):
        replace_schedule_assignments(self.schedule, self._full_assignments())
        lunch_slot = self.schedule.slots.get(
            service_date=date(2026, 7, 1),
            meal_period='lunch',
        )
        # First half includes day 1 lunch → chicken+rice+dal
        priced = compute_slot_final_price(
            lunch_slot,
            per_meal_operational_cost=Decimal('31.00'),
            profit_percent=Decimal('10.00'),
        )
        # 20+8+3=31, profit 3.10, op 31 → 65.10
        self.assertEqual(priced['final_meal_price_snapshot'], Decimal('65.10'))

        # Find a dinner in second half (alu+rice)
        dinner_slot = None
        for slot in self.schedule.slots.filter(meal_period='dinner'):
            names = {item.ingredient.name for item in slot.items.all()}
            if names == {'Alu Vorta', 'Rice'}:
                dinner_slot = slot
                break
        self.assertIsNotNone(dinner_slot)
        dinner_priced = compute_slot_final_price(
            dinner_slot,
            per_meal_operational_cost=Decimal('31.00'),
            profit_percent=Decimal('10.00'),
        )
        # 4+8=12, profit 1.20, op 31 → 44.20
        self.assertEqual(dinner_priced['final_meal_price_snapshot'], Decimal('44.20'))
        self.assertNotEqual(
            priced['final_meal_price_snapshot'],
            dinner_priced['final_meal_price_snapshot'],
        )

    def test_publish_locks_prices_and_ingredient_change_ignored(self):
        replace_schedule_assignments(self.schedule, self._full_assignments())
        publish_schedule(self.schedule)
        lunch = MonthlyMenuSlot.objects.get(
            schedule=self.schedule,
            service_date=date(2026, 7, 1),
            meal_period='lunch',
        )
        locked = lunch.final_meal_price_snapshot
        self.assertIsNotNone(locked)

        self.chicken.cost_per_customer = Decimal('99.00')
        self.chicken.save(update_fields=['cost_per_customer', 'updated_at'])
        lunch.refresh_from_db()
        self.assertEqual(lunch.final_meal_price_snapshot, locked)

    def test_unpublish_clears_snapshots(self):
        replace_schedule_assignments(self.schedule, self._full_assignments())
        publish_schedule(self.schedule)
        unpublish_schedule(self.schedule)
        lunch = MonthlyMenuSlot.objects.get(
            schedule=self.schedule,
            service_date=date(2026, 7, 1),
            meal_period='lunch',
        )
        self.assertIsNone(lunch.final_meal_price_snapshot)

    def test_publish_package_a_does_not_change_package_b(self):
        other = MealCategory.objects.create(
            meal_name='Regular Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('regular.jpg'),
        )
        plan_b = MealCyclePlan.objects.create(
            cycle=self.cycle,
            meal_category=other,
            profit_percent=Decimal('10.00'),
        )
        total = self.cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=plan_b,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total,
        )
        MealCyclePlanLine.objects.create(
            plan=plan_b,
            ingredient=self.rice,
            product_role=MealCyclePlanLine.ProductRole.SIDE,
            servings_count=total,
        )
        finalize_plan(plan_b)
        schedule_b = create_schedule_for_plan(plan_b)
        keys = expected_slot_keys(2026, 7)
        assignments_b = [
            {
                'service_date': d,
                'meal_period': p,
                'ingredient_ids': [self.chicken.id, self.rice.id],
            }
            for d, p in keys
        ]
        replace_schedule_assignments(schedule_b, assignments_b)
        publish_schedule(schedule_b)
        slot_b_before = list(
            MonthlyMenuSlot.objects.filter(schedule=schedule_b).values_list(
                'id',
                'final_meal_price_snapshot',
                'service_date',
                'meal_period',
            )
        )

        replace_schedule_assignments(self.schedule, self._full_assignments())
        publish_schedule(self.schedule)

        slot_b_after = list(
            MonthlyMenuSlot.objects.filter(schedule=schedule_b).values_list(
                'id',
                'final_meal_price_snapshot',
                'service_date',
                'meal_period',
            )
        )
        self.assertEqual(slot_b_before, slot_b_after)
        schedule_b.refresh_from_db()
        self.assertTrue(schedule_b.is_published)

    def test_apply_sync_mutates_only_target(self):
        other = MealCategory.objects.create(
            meal_name='Student Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('student.jpg'),
        )
        plan_b = MealCyclePlan.objects.create(
            cycle=self.cycle,
            meal_category=other,
            profit_percent=Decimal('10.00'),
        )
        total = self.cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=plan_b,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total,
        )
        MealCyclePlanLine.objects.create(
            plan=plan_b,
            ingredient=self.rice,
            product_role=MealCyclePlanLine.ProductRole.SIDE,
            servings_count=total,
        )
        finalize_plan(plan_b)
        schedule_b = create_schedule_for_plan(plan_b)

        replace_schedule_assignments(self.schedule, self._full_assignments())
        source_fingerprint = list(
            MonthlyMenuSlotItem.objects.filter(slot__schedule=self.schedule)
            .order_by('slot__service_date', 'slot__meal_period', 'ingredient_id')
            .values_list('slot__service_date', 'slot__meal_period', 'ingredient_id')
        )

        apply_sync_suggestion(schedule_b, source=self.schedule)

        source_after = list(
            MonthlyMenuSlotItem.objects.filter(slot__schedule=self.schedule)
            .order_by('slot__service_date', 'slot__meal_period', 'ingredient_id')
            .values_list('slot__service_date', 'slot__meal_period', 'ingredient_id')
        )
        self.assertEqual(source_fingerprint, source_after)
        self.assertTrue(schedule_b.slots.exists())


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SlotPriceDeliveryChargeTests(TestCase):
    def setUp(self):
        from unittest.mock import patch

        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_user = User.objects.create_user(
            username='slot_pay_c',
            email='slot_pay_c@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1719999001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.admin_user = User.objects.create_user(
            username='slot_pay_a',
            email='slot_pay_a@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)

        self.meal = MealCategory.objects.create(
            meal_name='Daily Lunch',
            total_price=Decimal('50.00'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            meal_thumbnail=make_test_image('daily.jpg'),
            is_active=True,
        )
        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()
        self.wallet = get_or_create_wallet(self.customer)
        credit_wallet(self.wallet, Decimal('500.00'))

    def _priced_slot(self, meal, service_date, meal_period, price):
        cycle, _ = MealCycle.objects.get_or_create(
            year=service_date.year,
            month=service_date.month,
        )
        plan, _ = MealCyclePlan.objects.get_or_create(
            cycle=cycle,
            meal_category=meal,
            defaults={
                'status': MealCyclePlan.Status.FINALIZED,
                'finalized_at': timezone.now(),
                'snapshot_total_cost': Decimal('50.00'),
                'snapshot_per_meal_rate': Decimal('50.00'),
            },
        )
        if plan.status != MealCyclePlan.Status.FINALIZED:
            plan.status = MealCyclePlan.Status.FINALIZED
            plan.finalized_at = timezone.now()
            plan.snapshot_total_cost = Decimal('50.00')
            plan.snapshot_per_meal_rate = Decimal('50.00')
            plan.save()
        schedule, _ = MonthlyMenuSchedule.objects.get_or_create(
            plan=plan,
            defaults={
                'status': MonthlyMenuSchedule.Status.PUBLISHED,
                'published_at': timezone.now(),
            },
        )
        if not schedule.is_published:
            schedule.status = MonthlyMenuSchedule.Status.PUBLISHED
            schedule.published_at = timezone.now()
            schedule.save()
        slot, _ = MonthlyMenuSlot.objects.update_or_create(
            schedule=schedule,
            service_date=service_date,
            meal_period=meal_period,
            defaults={
                'final_meal_price_snapshot': price,
                'ingredient_cost_snapshot': price - Decimal('31.00'),
                'operational_cost_snapshot': Decimal('31.00'),
                'profit_snapshot': Decimal('0.00'),
            },
        )
        return slot

    def test_charge_uses_slot_price_not_order_average(self):
        from unittest.mock import patch

        with patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5)):
            order = create_meal_order(self.customer, self.meal)
        self.assertEqual(order.per_meal_price_snapshot, Decimal('50.00'))
        delivery = order.deliveries.get()
        self._priced_slot(self.meal, delivery.service_date, delivery.meal_period, Decimal('62.00'))
        balance_before = self.wallet.balance

        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            marked = mark_delivery(delivery, 'delivered', marked_by=self.admin_user)

        marked.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(marked.charged_amount, Decimal('62.00'))
        self.assertEqual(marked.wallet_transaction.amount, Decimal('62.00'))
        self.assertEqual(self.wallet.balance, balance_before - Decimal('62.00'))
        self.assertEqual(marked.wallet_transaction.metadata.get('charge_source'), 'slot_final_price')

    def test_missing_slot_price_rejects_charge(self):
        from unittest.mock import patch

        with patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5)):
            order = create_meal_order(self.customer, self.meal)
        delivery = order.deliveries.get()
        delivery.status = OrderDelivery.DeliveryStatus.DELIVERED
        delivery.save(update_fields=['status', 'updated_at'])

        with self.assertRaises(MealPaymentError) as ctx:
            charge_delivered_meal(delivery)
        self.assertEqual(ctx.exception.code, 'MEAL_SLOT_PRICE_MISSING')
