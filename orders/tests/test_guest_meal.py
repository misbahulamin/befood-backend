from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from meals.models import MealCategory
from orders.models import GuestMealOrder, OrderDelivery, OrderWalletSettings
from orders.services.guest_meal import (
    GuestMealNotEligibleError,
    GuestMealQuotaError,
    GuestMealValidationError,
    GuestMealWalletError,
    create_guest_meal_order,
    guest_usage_summary,
    preview_guest_meal,
    resolve_guest_pricing,
)
from orders.services.meal_demand import build_kitchen_requirement, get_demand
from orders.services.order_delivery import mark_delivery
from orders.services.subscription_service import subscribe_customer
from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot
from user_management.models import AdminProfile, CustomerProfile
from user_management.services.admin_customer import build_activity_events
from wallet.models import WalletTransaction
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class GuestMealOrderTests(APITestCase):
    def setUp(self):
        self.today = date(2026, 9, 15)
        self.tz = ZoneInfo('Asia/Dhaka')
        self.now = datetime(2026, 9, 15, 10, 0, 0, tzinfo=self.tz)

        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=self.today,
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._guest_today_patcher = patch(
            'orders.services.guest_meal.business_today',
            return_value=self.today,
        )
        self._guest_today_patcher.start()
        self.addCleanup(self._guest_today_patcher.stop)
        self._cutoff_patcher = patch(
            'orders.services.guest_meal.is_past_meal_cutoff',
            return_value=False,
        )
        self._cutoff_patcher.start()
        self.addCleanup(self._cutoff_patcher.stop)
        # ensure_subscription_deliveries binds is_past_meal_cutoff at import time.
        self._sub_cutoff_patcher = patch(
            'orders.services.subscription_service.is_past_meal_cutoff',
            return_value=False,
        )
        self._sub_cutoff_patcher.start()
        self.addCleanup(self._sub_cutoff_patcher.stop)
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)
        # Align auto_now / meal-off deadline evaluation with the patched business day.
        self._now_patcher = patch(
            'django.utils.timezone.now',
            return_value=self.now,
        )
        self._now_patcher.start()
        self.addCleanup(self._now_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.customer_user = User.objects.create_user(
            username='guest_meal_customer',
            email='guest_meal@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712999001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.customer_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.other_user = User.objects.create_user(
            username='guest_meal_other',
            email='guest_meal_other@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.other_user.groups.add(customer_group)
        self.other = CustomerProfile.objects.create(
            user=self.other_user,
            phone='1712999002',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.plan = MealCategory.objects.create(
            meal_name='Guest Meal Plan',
            description='Plan',
            meal_thumbnail=make_test_image(),
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('1800.00'),
            is_active=True,
            is_subscribable=True,
        )
        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('100.00')
        settings_obj.low_balance_reminder_threshold = Decimal('50.00')
        settings_obj.meal_stop_threshold = Decimal('200.00')
        settings_obj.guest_meal_box_price = Decimal('10.00')
        settings_obj.guest_meal_monthly_limit = 10
        settings_obj.save()

        wallet = get_or_create_wallet(self.customer)
        credit_wallet(wallet, Decimal('1000.00'), note='fund')
        self.subscription = subscribe_customer(
            self.customer, self.plan, today=self.today
        )
        ensure_priced_delivery_slot(
            self.plan, self.today, 'lunch', price=Decimal('60.00')
        )
        ensure_priced_delivery_slot(
            self.plan, self.today, 'dinner', price=Decimal('60.00')
        )
        ensure_priced_delivery_slot(
            self.plan, self.today + timedelta(days=1), 'lunch', price=Decimal('60.00')
        )

    def _create(self, *, quantity=1, meal_period='lunch', service_date=None, key=None):
        return create_guest_meal_order(
            self.customer,
            service_date=service_date or self.today,
            meal_period=meal_period,
            quantity=quantity,
            idempotency_key=key,
        )

    def test_active_subscriber_can_create(self):
        order, payload = self._create(quantity=2)
        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.base_meal_price, Decimal('60.00'))
        self.assertEqual(order.box_price, Decimal('10.00'))
        self.assertEqual(order.unit_price, Decimal('70.00'))
        self.assertEqual(order.total_amount, Decimal('140.00'))
        self.assertEqual(payload['status'], GuestMealOrder.Status.SCHEDULED)
        self.assertIsNotNone(order.wallet_transaction_id)
        self.assertEqual(order.wallet_transaction.metadata.get('purpose'), 'guest_meal')
        self.assertEqual(
            order.wallet_transaction.type, WalletTransaction.Type.PAYMENT
        )

    def test_no_subscription_rejected(self):
        other_wallet = get_or_create_wallet(self.other)
        credit_wallet(other_wallet, Decimal('1000.00'), note='fund')
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            create_guest_meal_order(
                self.other,
                service_date=self.today,
                meal_period='lunch',
                quantity=1,
            )
        self.assertEqual(ctx.exception.code, 'NO_ACTIVE_SUBSCRIPTION')
        self.assertEqual(GuestMealOrder.objects.filter(customer=self.other).count(), 0)

    def test_cancelled_subscription_rejected(self):
        self.subscription.status = self.subscription.Status.CANCELLED
        self.subscription.save(update_fields=['status', 'updated_at'])
        with self.assertRaises(GuestMealNotEligibleError):
            self._create()
        self.assertEqual(GuestMealOrder.objects.count(), 0)

    def test_pricing_helpers_and_snapshot_stable(self):
        base, box, unit, total = resolve_guest_pricing(
            meal_id=self.plan.id,
            service_date=self.today,
            meal_period='lunch',
            quantity=2,
        )
        self.assertEqual((base, box, unit, total), (
            Decimal('60.00'), Decimal('10.00'), Decimal('70.00'), Decimal('140.00'),
        ))
        order, _ = self._create(quantity=1)
        settings_obj = OrderWalletSettings.load()
        settings_obj.guest_meal_box_price = Decimal('15.00')
        settings_obj.save(update_fields=['guest_meal_box_price', 'updated_at'])
        ensure_priced_delivery_slot(
            self.plan, self.today, 'lunch', price=Decimal('80.00')
        )
        order.refresh_from_db()
        self.assertEqual(order.base_meal_price, Decimal('60.00'))
        self.assertEqual(order.box_price, Decimal('10.00'))
        self.assertEqual(order.unit_price, Decimal('70.00'))

    def test_missing_price_rejected(self):
        future = self.today + timedelta(days=5)
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            create_guest_meal_order(
                self.customer,
                service_date=future,
                meal_period='lunch',
                quantity=1,
            )
        self.assertEqual(ctx.exception.code, 'PRICE_UNAVAILABLE')

    def test_wallet_threshold_and_exact_floor(self):
        # recharge 1000, threshold 200 → max spend 800; total 70*12 would fail anyway
        # exact floor: spend so recharge_after == 200
        settings_obj = OrderWalletSettings.load()
        settings_obj.meal_stop_threshold = Decimal('200.00')
        settings_obj.save(update_fields=['meal_stop_threshold', 'updated_at'])

        # total 800 → after 200 OK (inclusive)
        # unit 70 → quantity 11 exceeds monthly; use qty that totals 800 exactly:
        # set box 0 and base 800 for one unit
        ensure_priced_delivery_slot(
            self.plan, self.today, 'dinner', price=Decimal('800.00')
        )
        settings_obj.guest_meal_box_price = Decimal('0.00')
        settings_obj.save(update_fields=['guest_meal_box_price', 'updated_at'])
        order, _ = self._create(quantity=1, meal_period='dinner')
        self.assertEqual(order.total_amount, Decimal('800.00'))

        wallet = get_or_create_wallet(self.customer)
        wallet.refresh_from_db()
        self.assertEqual(wallet.recharge_balance, Decimal('200.00'))

        ensure_priced_delivery_slot(
            self.plan, self.today + timedelta(days=1), 'dinner', price=Decimal('1.00')
        )
        with self.assertRaises(GuestMealWalletError) as ctx:
            create_guest_meal_order(
                self.customer,
                service_date=self.today + timedelta(days=1),
                meal_period='dinner',
                quantity=1,
            )
        self.assertEqual(ctx.exception.code, 'MEAL_STOP_FLOOR')

    def test_debit_fail_no_guest_row(self):
        wallet = get_or_create_wallet(self.customer)
        wallet.recharge_balance = Decimal('0.00')
        wallet.commission_balance = Decimal('0.00')
        wallet.balance = Decimal('0.00')
        wallet.save()
        with self.assertRaises(GuestMealWalletError):
            self._create()
        self.assertEqual(GuestMealOrder.objects.count(), 0)

    def test_monthly_quota(self):
        for _ in range(10):
            self._create(quantity=1, meal_period='lunch')
        with self.assertRaises(GuestMealQuotaError):
            self._create(quantity=1, meal_period='dinner')
        usage = guest_usage_summary(self.customer)
        self.assertEqual(usage['used_quantity'], 10)
        self.assertEqual(usage['remaining_quantity'], 0)

    def test_prior_month_excluded(self):
        old = GuestMealOrder.objects.create(
            customer=self.customer,
            subscription=self.subscription,
            service_date=self.today - timedelta(days=40),
            meal_period='lunch',
            quantity=5,
            base_meal_price=Decimal('60.00'),
            box_price=Decimal('10.00'),
            unit_price=Decimal('70.00'),
            total_amount=Decimal('350.00'),
            status=GuestMealOrder.Status.DELIVERED,
        )
        GuestMealOrder.objects.filter(pk=old.pk).update(
            created_at=datetime(2026, 8, 20, 12, 0, tzinfo=self.tz)
        )
        usage = guest_usage_summary(self.customer)
        self.assertEqual(usage['used_quantity'], 0)
        self._create(quantity=10)
        usage = guest_usage_summary(self.customer)
        self.assertEqual(usage['used_quantity'], 10)

    def test_eligibility_period_date_cutoff(self):
        with self.assertRaises(GuestMealValidationError):
            create_guest_meal_order(
                self.customer,
                service_date=self.today - timedelta(days=1),
                meal_period='lunch',
                quantity=1,
            )
        with self.assertRaises(GuestMealValidationError):
            preview_guest_meal(
                self.customer,
                service_date=self.today,
                meal_period='brunch',
                quantity=1,
            )
        lunch_plan = MealCategory.objects.create(
            meal_name='Lunch Only',
            description='x',
            meal_thumbnail=make_test_image('lunch.jpg'),
            meal_period=MealCategory.MealPeriod.LUNCH,
            total_price=Decimal('1800.00'),
            is_active=True,
            is_subscribable=True,
        )
        self.subscription.status = self.subscription.Status.CANCELLED
        self.subscription.save(update_fields=['status', 'updated_at'])
        lunch_sub = subscribe_customer(self.customer, lunch_plan, today=self.today)
        ensure_priced_delivery_slot(lunch_plan, self.today, 'lunch', Decimal('60.00'))
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            create_guest_meal_order(
                self.customer,
                service_date=self.today,
                meal_period='dinner',
                quantity=1,
            )
        self.assertEqual(ctx.exception.code, 'UNSUPPORTED_MEAL_PERIOD')
        self.assertEqual(lunch_sub.status, lunch_sub.Status.ACTIVE)

        with patch('orders.services.guest_meal.is_past_meal_cutoff', return_value=True):
            with self.assertRaises(GuestMealNotEligibleError) as cut:
                create_guest_meal_order(
                    self.customer,
                    service_date=self.today,
                    meal_period='lunch',
                    quantity=1,
                )
            self.assertEqual(cut.exception.code, 'CUTOFF_PASSED')

    def test_api_usage_preview_create_list_detail_auth(self):
        usage = self.client.get('/api/v1/guest-meals/usage/')
        self.assertEqual(usage.status_code, status.HTTP_200_OK)
        self.assertEqual(usage.data['monthly_limit'], 10)

        preview = self.client.post(
            '/api/v1/guest-meals/preview/',
            {'date': self.today.isoformat(), 'meal_period': 'lunch', 'quantity': 2},
            format='json',
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data['total_price'], '140.00')
        self.assertTrue(preview.data['eligible'])
        wallet_before = get_or_create_wallet(self.customer)
        bal = wallet_before.balance

        created = self.client.post(
            '/api/v1/guest-meals/',
            {'date': self.today.isoformat(), 'meal_period': 'lunch', 'quantity': 2},
            format='json',
            HTTP_IDEMPOTENCY_KEY='guest-key-1',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        public_id = created.data['public_id']
        wallet_before.refresh_from_db()
        self.assertEqual(wallet_before.balance, bal - Decimal('140.00'))

        replay = self.client.post(
            '/api/v1/guest-meals/',
            {'date': self.today.isoformat(), 'meal_period': 'lunch', 'quantity': 2},
            format='json',
            HTTP_IDEMPOTENCY_KEY='guest-key-1',
        )
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data['idempotent_replay'])
        self.assertEqual(GuestMealOrder.objects.count(), 1)

        conflict = self.client.post(
            '/api/v1/guest-meals/',
            {'date': self.today.isoformat(), 'meal_period': 'dinner', 'quantity': 1},
            format='json',
            HTTP_IDEMPOTENCY_KEY='guest-key-1',
        )
        self.assertEqual(conflict.status_code, status.HTTP_409_CONFLICT)

        listed = self.client.get('/api/v1/guest-meals/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data['results']), 1)

        detail = self.client.get(f'/api/v1/guest-meals/{public_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        other_client = APIClient()
        other_client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        denied = other_client.get(f'/api/v1/guest-meals/{public_id}/')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_preview_does_not_debit(self):
        wallet = get_or_create_wallet(self.customer)
        before = wallet.balance
        preview_guest_meal(
            self.customer,
            service_date=self.today,
            meal_period='lunch',
            quantity=1,
        )
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before)

    def test_demand_and_deliver_no_recharge_guest(self):
        order, _ = self._create(quantity=2)
        demand = get_demand(self.today, 'lunch')
        # at least one live delivery + 2 guest
        self.assertGreaterEqual(demand.final_cooking_count, 3)
        pkg = next(p for p in demand.packages if p.package_id == self.plan.id)
        self.assertGreaterEqual(pkg.final_cooking_count, 3)
        # Additive breakdown reconciles without changing inclusive totals.
        self.assertEqual(demand.guest_meal_count, 2)
        self.assertEqual(
            demand.subscription_final_cooking_count + demand.guest_meal_count,
            demand.final_cooking_count,
        )
        self.assertEqual(pkg.guest_meal_count, 2)
        self.assertEqual(
            pkg.subscription_final_cooking_count + pkg.guest_meal_count,
            pkg.final_cooking_count,
        )
        kitchen = build_kitchen_requirement(self.today, 'lunch')
        self.assertEqual(kitchen['guest_meal_count'], 2)
        self.assertEqual(
            kitchen['subscription_final_cooking_count'] + kitchen['guest_meal_count'],
            kitchen['final_cooking_count'],
        )

        delivery = order.delivery
        self.assertIsNotNone(delivery)
        wallet = get_or_create_wallet(self.customer)
        before = wallet.balance
        # Ensure enough for regular meal charge (60)
        mark_delivery(delivery, OrderDelivery.DeliveryStatus.DELIVERED)
        wallet.refresh_from_db()
        # Charged regular slot only (60), not guest 140 again
        self.assertEqual(before - wallet.balance, Decimal('60.00'))
        order.refresh_from_db()
        self.assertEqual(order.status, GuestMealOrder.Status.DELIVERED)

        from admin_wallet.models import MealProfitTransaction

        guest_row = MealProfitTransaction.objects.get(guest_meal_order=order)
        self.assertEqual(guest_row.meal_kind, MealProfitTransaction.MealKind.GUEST)
        self.assertEqual(guest_row.quantity, 2)
        self.assertEqual(guest_row.meal_price, order.total_amount)
        # Idempotent: second mark-delivered does not duplicate guest profit or re-debit.
        before_again = wallet.balance
        mark_delivery(delivery, OrderDelivery.DeliveryStatus.DELIVERED)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before_again)
        self.assertEqual(
            MealProfitTransaction.objects.filter(guest_meal_order=order).count(),
            1,
        )

    def test_cancelled_guest_excluded_from_demand_breakdown(self):
        order, _ = self._create(quantity=3)
        order.status = GuestMealOrder.Status.CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        demand = get_demand(self.today, 'lunch')
        self.assertEqual(demand.guest_meal_count, 0)
        self.assertEqual(
            demand.subscription_final_cooking_count,
            demand.final_cooking_count,
        )

    def test_activity_includes_guest_meal_ordered(self):
        order, _ = self._create(quantity=1)
        events = build_activity_events(self.customer)
        guest_events = [e for e in events if e['event_type'] == 'guest_meal_ordered']
        self.assertEqual(len(guest_events), 1)
        self.assertEqual(
            guest_events[0]['refs']['guest_meal_public_id'], str(order.public_id)
        )
        self.assertEqual(guest_events[0]['refs']['quantity'], 1)

    def _lunch_delivery(self):
        return OrderDelivery.objects.get(
            subscription=self.subscription,
            service_date=self.today,
            meal_period='lunch',
        )

    def _dinner_delivery(self):
        return OrderDelivery.objects.get(
            subscription=self.subscription,
            service_date=self.today,
            meal_period='dinner',
        )

    def _mark_customer_meal_off(self, delivery):
        delivery.status = OrderDelivery.DeliveryStatus.SKIPPED
        delivery.skip_source = OrderDelivery.SkipSource.CUSTOMER
        delivery.marked_at = timezone.now()
        delivery.save(
            update_fields=['status', 'skip_source', 'marked_at', 'updated_at']
        )

    def test_personal_meal_off_blocks_guest_lunch_only(self):
        self._mark_customer_meal_off(self._lunch_delivery())
        wallet = get_or_create_wallet(self.customer)
        before_balance = wallet.balance
        before_usage = guest_usage_summary(self.customer)['used_quantity']
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            self._create(meal_period='lunch')
        self.assertEqual(ctx.exception.code, 'PERSONAL_MEAL_OFF')
        # Dinner still allowed while lunch is OFF.
        order, _ = self._create(meal_period='dinner')
        self.assertEqual(order.meal_period, 'dinner')
        wallet.refresh_from_db()
        self.assertEqual(GuestMealOrder.objects.filter(meal_period='lunch').count(), 0)
        self.assertLess(wallet.balance, before_balance)
        self.assertEqual(
            guest_usage_summary(self.customer)['used_quantity'],
            before_usage + 1,
        )

    def test_personal_meal_off_blocks_guest_dinner_only(self):
        self._mark_customer_meal_off(self._dinner_delivery())
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            self._create(meal_period='dinner')
        self.assertEqual(ctx.exception.code, 'PERSONAL_MEAL_OFF')
        order, _ = self._create(meal_period='lunch')
        self.assertEqual(order.meal_period, 'lunch')

    def test_both_off_blocks_both_periods(self):
        self._mark_customer_meal_off(self._lunch_delivery())
        self._mark_customer_meal_off(self._dinner_delivery())
        with self.assertRaises(GuestMealNotEligibleError) as lunch_ctx:
            self._create(meal_period='lunch')
        with self.assertRaises(GuestMealNotEligibleError) as dinner_ctx:
            self._create(meal_period='dinner')
        self.assertEqual(lunch_ctx.exception.code, 'PERSONAL_MEAL_OFF')
        self.assertEqual(dinner_ctx.exception.code, 'PERSONAL_MEAL_OFF')
        self.assertEqual(GuestMealOrder.objects.count(), 0)

    def test_admin_system_skip_alone_does_not_trigger_personal_meal_off(self):
        lunch = self._lunch_delivery()
        lunch.status = OrderDelivery.DeliveryStatus.SKIPPED
        lunch.skip_source = OrderDelivery.SkipSource.SYSTEM
        lunch.save(update_fields=['status', 'skip_source', 'updated_at'])
        # Create requires scheduled delivery — system skip uses DELIVERY_UNAVAILABLE.
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            self._create(meal_period='lunch')
        self.assertEqual(ctx.exception.code, 'DELIVERY_UNAVAILABLE')
        self.assertNotEqual(ctx.exception.code, 'PERSONAL_MEAL_OFF')

    def test_api_personal_meal_off_returns_422(self):
        self._mark_customer_meal_off(self._lunch_delivery())
        wallet = get_or_create_wallet(self.customer)
        before = wallet.balance
        before_txns = WalletTransaction.objects.filter(wallet=wallet).count()
        response = self.client.post(
            '/api/v1/guest-meals/preview/',
            {'date': self.today.isoformat(), 'meal_period': 'lunch', 'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data['error_code'], 'PERSONAL_MEAL_OFF')
        create_resp = self.client.post(
            '/api/v1/guest-meals/',
            {'date': self.today.isoformat(), 'meal_period': 'lunch', 'quantity': 1},
            format='json',
        )
        self.assertEqual(create_resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(create_resp.data['error_code'], 'PERSONAL_MEAL_OFF')
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before)
        self.assertEqual(
            WalletTransaction.objects.filter(wallet=wallet).count(), before_txns
        )
        self.assertEqual(guest_usage_summary(self.customer)['used_quantity'], 0)

    def test_create_revalidates_meal_off_after_preview(self):
        preview = preview_guest_meal(
            self.customer,
            service_date=self.today,
            meal_period='lunch',
            quantity=1,
        )
        self.assertTrue(preview['eligible'])
        self._mark_customer_meal_off(self._lunch_delivery())
        wallet = get_or_create_wallet(self.customer)
        before = wallet.balance
        with self.assertRaises(GuestMealNotEligibleError) as ctx:
            self._create(meal_period='lunch')
        self.assertEqual(ctx.exception.code, 'PERSONAL_MEAL_OFF')
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before)
        self.assertEqual(GuestMealOrder.objects.count(), 0)

    def test_missing_delivery_stop_rejects_before_debit(self):
        wallet = get_or_create_wallet(self.customer)
        before = wallet.balance
        with patch(
            'orders.services.guest_meal._resolve_linked_delivery',
            return_value=None,
        ):
            with self.assertRaises(GuestMealNotEligibleError) as ctx:
                self._create()
        self.assertEqual(ctx.exception.code, 'DELIVERY_UNAVAILABLE')
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before)
        self.assertEqual(GuestMealOrder.objects.count(), 0)
        self.assertEqual(guest_usage_summary(self.customer)['used_quantity'], 0)

    def test_meal_off_blocked_when_scheduled_guest_exists(self):
        from orders.services.meal_off import MealOffError, can_meal_off, customer_meal_off

        order, _ = self._create(meal_period='lunch', quantity=2)
        lunch = self._lunch_delivery()
        self.assertFalse(can_meal_off(lunch))
        with self.assertRaises(MealOffError):
            customer_meal_off(lunch, user=self.customer_user)
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        order.refresh_from_db()
        self.assertEqual(order.status, GuestMealOrder.Status.SCHEDULED)
        # Dinner meal-off still allowed when only lunch guest exists.
        dinner = self._dinner_delivery()
        self.assertTrue(can_meal_off(dinner))


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class GuestMealConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.today = date(2026, 9, 15)
        self.tz = ZoneInfo('Asia/Dhaka')
        self.now = datetime(2026, 9, 15, 10, 0, 0, tzinfo=self.tz)
        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=self.today,
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._guest_today_patcher = patch(
            'orders.services.guest_meal.business_today',
            return_value=self.today,
        )
        self._guest_today_patcher.start()
        self.addCleanup(self._guest_today_patcher.stop)
        self._cutoff_patcher = patch(
            'orders.services.guest_meal.is_past_meal_cutoff',
            return_value=False,
        )
        self._cutoff_patcher.start()
        self.addCleanup(self._cutoff_patcher.stop)
        self._sub_cutoff_patcher = patch(
            'orders.services.subscription_service.is_past_meal_cutoff',
            return_value=False,
        )
        self._sub_cutoff_patcher.start()
        self.addCleanup(self._sub_cutoff_patcher.stop)
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)
        self._now_patcher = patch(
            'django.utils.timezone.now',
            return_value=self.now,
        )
        self._now_patcher.start()
        self.addCleanup(self._now_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        user = User.objects.create_user(
            username='guest_conc',
            email='guest_conc@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=user,
            phone='1712888001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.plan = MealCategory.objects.create(
            meal_name='Conc Plan',
            description='x',
            meal_thumbnail=make_test_image('conc.jpg'),
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('1800.00'),
            is_active=True,
            is_subscribable=True,
        )
        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('100.00')
        settings_obj.low_balance_reminder_threshold = Decimal('50.00')
        settings_obj.meal_stop_threshold = Decimal('0.00')
        settings_obj.guest_meal_box_price = Decimal('10.00')
        settings_obj.guest_meal_monthly_limit = 10
        settings_obj.save()
        credit_wallet(get_or_create_wallet(self.customer), Decimal('5000.00'), note='fund')
        subscribe_customer(self.customer, self.plan, today=self.today)
        ensure_priced_delivery_slot(self.plan, self.today, 'lunch', Decimal('60.00'))

        # Seed 9 units so only one more unit can succeed
        create_guest_meal_order(
            self.customer,
            service_date=self.today,
            meal_period='lunch',
            quantity=9,
        )

    def test_parallel_creates_cannot_exceed_quota(self):
        def _attempt():
            try:
                create_guest_meal_order(
                    self.customer,
                    service_date=self.today,
                    meal_period='lunch',
                    quantity=1,
                )
                return 'ok'
            except Exception as exc:
                return type(exc).__name__

        results = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_attempt) for _ in range(2)]
            for fut in as_completed(futures):
                results.append(fut.result())
        self.assertEqual(results.count('ok'), 1)
        usage = guest_usage_summary(self.customer)
        self.assertEqual(usage['used_quantity'], 10)
        connection.close()


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AdminGuestMealApiTests(GuestMealOrderTests):
    def setUp(self):
        super().setUp()
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='guest_meal_admin',
            email='guest_meal_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)
        self.admin_client = APIClient()
        self.admin_client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.admin_token.key}'
        )

    def test_admin_list_detail_and_summary_separates_orders_vs_boxes(self):
        self._create(quantity=2, key='admin-list-a')
        self._create(quantity=3, meal_period='dinner', key='admin-list-b')

        listed = self.admin_client.get('/api/v1/web/orders/guest-meals/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data['count'], 2)
        self.assertEqual(listed.data['summary']['order_count'], 2)
        self.assertEqual(listed.data['summary']['box_quantity'], 5)
        self.assertEqual(listed.data['summary']['scheduled_box_quantity'], 5)
        self.assertIn('revenue', listed.data['summary'])
        self.assertEqual(
            listed.data['summary']['prepaid_order_value'],
            listed.data['summary']['revenue'],
        )
        self.assertEqual(listed.data['summary']['delivered_recognized_revenue'], '0.00')
        self.assertEqual(listed.data['summary']['realized_guest_profit'], '0.00')
        row = listed.data['results'][0]
        self.assertIn('customer_name', row)
        self.assertIn('quantity', row)
        self.assertIn('total_amount', row)

        public_id = row['public_id']
        detail = self.admin_client.get(f'/api/v1/web/orders/guest-meals/{public_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['public_id'], public_id)
        self.assertEqual(detail.data['subscription_public_id'], str(self.subscription.public_id))

        filtered = self.admin_client.get(
            '/api/v1/web/orders/guest-meals/',
            {'service_date': self.today.isoformat(), 'meal_period': 'lunch'},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data['count'], 1)
        self.assertEqual(filtered.data['summary']['box_quantity'], 2)

    def test_customer_token_denied_for_admin_guest_meals(self):
        denied = self.client.get('/api/v1/web/orders/guest-meals/')
        self.assertIn(denied.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
