"""Low-balance resume must not retroactively restore past-cutoff meal slots."""

from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from meals.models import (
    Ingredient,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from orders.models import MealOffSettings, Order, OrderDelivery, OrderWalletSettings
from orders.services.meal_demand import build_kitchen_requirement, get_demand
from orders.services.meal_off import CUTOFF_PASSED_NOTE, system_skip_past_cutoff_deliveries_for_customer
from orders.services.wallet_balance_thresholds import (
    apply_meal_service_block,
    maybe_resume_after_wallet_credit,
    resume_meal_service_after_balance_recovery,
    run_wallet_threshold_check,
)
from user_management.models import CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (50, 50), 'red').save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _set_wallet_balance(wallet, amount: Decimal) -> None:
    amount = amount.quantize(Decimal('0.01'))
    wallet.balance = amount
    wallet.recharge_balance = amount
    wallet.commission_balance = Decimal('0.00')
    wallet.save(
        update_fields=[
            'balance',
            'recharge_balance',
            'commission_balance',
            'updated_at',
        ]
    )


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LowBalanceRechargeCutoffSkipTests(TestCase):
    def setUp(self):
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.settings_obj = MealOffSettings.load()
        self.settings_obj.timezone = 'Asia/Dhaka'
        self.settings_obj.lunch_off_time = time(2, 0)
        self.settings_obj.dinner_off_time = time(16, 0)
        self.settings_obj.save()

        wallet_settings = OrderWalletSettings.load()
        wallet_settings.meal_stop_threshold = Decimal('100.00')
        wallet_settings.save(update_fields=['meal_stop_threshold', 'updated_at'])

        self.meal = MealCategory.objects.create(
            meal_name='Resume Package',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image(),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.rice = Ingredient.objects.create(
            name='Resume Rice',
            price_per_kg=Decimal('80.00'),
            customers_per_kg=Decimal('5.00'),
            is_active=True,
        )
        self.service_date = date(2026, 9, 13)
        self._seed_menu()

    def _seed_menu(self):
        cycle = MealCycle.objects.create(year=2026, month=9)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=self.meal,
            status=MealCyclePlan.Status.FINALIZED,
        )
        schedule = MonthlyMenuSchedule.objects.create(
            plan=plan,
            status=MonthlyMenuSchedule.Status.PUBLISHED,
        )
        for period in (OrderDelivery.MealPeriod.LUNCH, OrderDelivery.MealPeriod.DINNER):
            slot = MonthlyMenuSlot.objects.create(
                schedule=schedule,
                service_date=self.service_date,
                meal_period=period,
            )
            MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=self.rice)

    def _make_customer(self, suffix: str) -> CustomerProfile:
        user = User.objects.create_user(
            username=f'resume_cutoff_{suffix}',
            email=f'resume_cutoff_{suffix}@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        user.groups.add(self.customer_group)
        return CustomerProfile.objects.create(
            user=user,
            phone=f'{1700000000 + abs(hash(suffix)) % 90000000:d}'[:10],
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

    def _get_or_create_order(self, customer: CustomerProfile) -> Order:
        order, _ = Order.objects.get_or_create(
            customer=customer,
            order_month='2026-09',
            defaults={
                'meal': self.meal,
                'meal_name_snapshot': self.meal.meal_name,
                'meal_type_snapshot': self.meal.meal_type,
                'meal_period_snapshot': self.meal.meal_period,
                'total_price_snapshot': self.meal.total_price,
                'per_meal_price_snapshot': Decimal('100.00'),
                'order_status': Order.OrderStatus.ACTIVE,
                'order_start_date': self.service_date,
                'order_end_date': self.service_date,
                'service_days_count': 1,
            },
        )
        return order

    def _create_delivery(
        self,
        customer: CustomerProfile,
        meal_period: str,
        *,
        skipped: bool = False,
        skip_source=None,
    ) -> OrderDelivery:
        order = self._get_or_create_order(customer)
        return OrderDelivery.objects.create(
            order=order,
            service_date=self.service_date,
            meal_period=meal_period,
            status=(
                OrderDelivery.DeliveryStatus.SKIPPED
                if skipped
                else OrderDelivery.DeliveryStatus.SCHEDULED
            ),
            skip_source=skip_source,
        )

    def test_block_when_balance_below_threshold(self):
        customer = self._make_customer('low')
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('50.00'))
        apply_meal_service_block(customer)
        customer.refresh_from_db()
        self.assertTrue(customer.meal_service_blocked_low_balance)

    def test_resume_before_lunch_cutoff_keeps_lunch_scheduled(self):
        customer = self._make_customer('before_lunch')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 1, 30, tzinfo=ZoneInfo('Asia/Dhaka'))
        self.assertTrue(
            resume_meal_service_after_balance_recovery(customer, now=now)
        )
        customer.refresh_from_db()
        lunch.refresh_from_db()
        self.assertFalse(customer.meal_service_blocked_low_balance)
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_resume_after_lunch_cutoff_skips_lunch_without_raising_cooking_count(self):
        baseline_customer = self._make_customer('baseline')
        self._create_delivery(baseline_customer, OrderDelivery.MealPeriod.LUNCH)

        blocked_customer = self._make_customer('late')
        lunch = self._create_delivery(blocked_customer, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(blocked_customer)
        wallet = get_or_create_wallet(blocked_customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        before = get_demand(
            self.service_date,
            OrderDelivery.MealPeriod.LUNCH,
            now=now,
            settings_obj=self.settings_obj,
        )
        self.assertEqual(before.final_cooking_count, 1)
        self.assertEqual(before.low_balance_blocked_count, 1)

        self.assertTrue(
            resume_meal_service_after_balance_recovery(blocked_customer, now=now)
        )
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(lunch.skip_source, OrderDelivery.SkipSource.SYSTEM)
        self.assertEqual(lunch.note, CUTOFF_PASSED_NOTE)

        after = get_demand(
            self.service_date,
            OrderDelivery.MealPeriod.LUNCH,
            now=now,
            settings_obj=self.settings_obj,
        )
        self.assertEqual(after.final_cooking_count, 1)
        self.assertEqual(after.low_balance_blocked_count, 0)
        self.assertEqual(after.meal_off_count, 1)

    def test_lunch_skipped_dinner_eligible_when_between_cutoffs(self):
        customer = self._make_customer('split')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        dinner = self._create_delivery(customer, OrderDelivery.MealPeriod.DINNER)
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        resume_meal_service_after_balance_recovery(customer, now=now)
        lunch.refresh_from_db()
        dinner.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SCHEDULED)

        dinner_demand = get_demand(
            self.service_date,
            OrderDelivery.MealPeriod.DINNER,
            now=now,
            settings_obj=self.settings_obj,
        )
        self.assertEqual(dinner_demand.final_cooking_count, 1)

    def test_both_meals_skipped_after_dinner_cutoff(self):
        customer = self._make_customer('both')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        dinner = self._create_delivery(customer, OrderDelivery.MealPeriod.DINNER)
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 18, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        resume_meal_service_after_balance_recovery(customer, now=now)
        lunch.refresh_from_db()
        dinner.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SKIPPED)

    def test_resume_exactly_at_cutoff_still_eligible(self):
        customer = self._make_customer('exact')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 2, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        resume_meal_service_after_balance_recovery(customer, now=now)
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_manual_meal_off_not_forced_on(self):
        customer = self._make_customer('manual_off')
        dinner = self._create_delivery(
            customer,
            OrderDelivery.MealPeriod.DINNER,
            skipped=True,
            skip_source=OrderDelivery.SkipSource.CUSTOMER,
        )
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        resume_meal_service_after_balance_recovery(customer, now=now)
        dinner.refresh_from_db()
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(dinner.skip_source, OrderDelivery.SkipSource.CUSTOMER)

    def test_skip_only_applies_to_today_service_date(self):
        customer = self._make_customer('tomorrow')
        tomorrow = date(2026, 9, 14)
        order = Order.objects.create(
            customer=customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_type_snapshot=self.meal.meal_type,
            meal_period_snapshot=self.meal.meal_period,
            total_price_snapshot=self.meal.total_price,
            per_meal_price_snapshot=Decimal('100.00'),
            order_status=Order.OrderStatus.ACTIVE,
            order_start_date=tomorrow,
            order_end_date=tomorrow,
            service_days_count=1,
            order_month='2026-09',
        )
        future_lunch = OrderDelivery.objects.create(
            order=order,
            service_date=tomorrow,
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        resume_meal_service_after_balance_recovery(customer, now=now)
        future_lunch.refresh_from_db()
        self.assertEqual(future_lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_idempotent_resume_and_skip_helper(self):
        customer = self._make_customer('idem')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))
        now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))

        self.assertTrue(resume_meal_service_after_balance_recovery(customer, now=now))
        self.assertFalse(resume_meal_service_after_balance_recovery(customer, now=now))
        self.assertEqual(
            system_skip_past_cutoff_deliveries_for_customer(customer, now=now),
            0,
        )
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(OrderDelivery.objects.filter(order__customer=customer).count(), 1)

    def test_kitchen_payload_stable_after_late_resume(self):
        self._create_delivery(self._make_customer('peer'), OrderDelivery.MealPeriod.LUNCH)
        blocked = self._make_customer('kitchen')
        self._create_delivery(blocked, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(blocked)
        wallet = get_or_create_wallet(blocked)
        _set_wallet_balance(wallet, Decimal('500.00'))

        now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        before = build_kitchen_requirement(
            self.service_date,
            OrderDelivery.MealPeriod.LUNCH,
            now=now,
            settings_obj=self.settings_obj,
        )
        resume_meal_service_after_balance_recovery(blocked, now=now)
        after = build_kitchen_requirement(
            self.service_date,
            OrderDelivery.MealPeriod.LUNCH,
            now=now,
            settings_obj=self.settings_obj,
        )
        self.assertEqual(before['final_cooking_count'], 1)
        self.assertEqual(after['final_cooking_count'], 1)
        rice_before = next(i for i in before['ingredients'] if i['name'] == 'Resume Rice')
        rice_after = next(i for i in after['ingredients'] if i['name'] == 'Resume Rice')
        self.assertEqual(rice_before['quantity'], rice_after['quantity'])

    @patch('orders.services.wallet_balance_thresholds.spendable_balance')
    def test_cron_resume_applies_cutoff_skip(self, mock_spendable):
        customer = self._make_customer('cron')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(customer)
        mock_spendable.return_value = Decimal('500.00')

        business_now = datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        with patch(
            'orders.services.wallet_balance_thresholds.business_today',
            return_value=self.service_date,
        ), patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=business_now,
        ):
            result = run_wallet_threshold_check(as_of=self.service_date)
        self.assertEqual(result.resumed, 1)
        lunch.refresh_from_db()
        customer.refresh_from_db()
        self.assertFalse(customer.meal_service_blocked_low_balance)
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)

    def test_maybe_resume_after_wallet_credit_uses_shared_path(self):
        customer = self._make_customer('credit')
        lunch = self._create_delivery(customer, OrderDelivery.MealPeriod.LUNCH)
        apply_meal_service_block(customer)
        wallet = get_or_create_wallet(customer)
        _set_wallet_balance(wallet, Decimal('500.00'))

        with patch(
            'orders.services.wallet_balance_thresholds.meal_off_business_now',
            return_value=datetime(2026, 9, 13, 8, 0, tzinfo=ZoneInfo('Asia/Dhaka')),
        ):
            self.assertTrue(maybe_resume_after_wallet_credit(customer))
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
