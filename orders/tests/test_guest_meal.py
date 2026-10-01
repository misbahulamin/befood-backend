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
from orders.services.meal_demand import get_demand
from orders.services.order_delivery import mark_delivery
from orders.services.subscription_service import subscribe_customer
from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot
from user_management.models import CustomerProfile
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
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

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

    def test_activity_includes_guest_meal_ordered(self):
        order, _ = self._create(quantity=1)
        events = build_activity_events(self.customer)
        guest_events = [e for e in events if e['event_type'] == 'guest_meal_ordered']
        self.assertEqual(len(guest_events), 1)
        self.assertEqual(
            guest_events[0]['refs']['guest_meal_public_id'], str(order.public_id)
        )
        self.assertEqual(guest_events[0]['refs']['quantity'], 1)


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class GuestMealConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.today = date(2026, 9, 15)
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
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

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
