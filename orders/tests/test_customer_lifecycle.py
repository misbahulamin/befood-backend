"""Unit tests for shared customer lifecycle classification."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from meals.models import MealCategory
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.customer_lifecycle import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_AT_RISK,
    LIFECYCLE_NEVER_SUBSCRIBED,
    LIFECYCLE_UNSUBSCRIBED,
    LIFECYCLE_WON_BACK,
    annotate_lifecycle,
    churn_date_for_subscription,
    classify_customer_lifecycle,
    count_low_balance_blocked_days,
    count_meal_off_days,
    estimate_one_day_meal_cost,
    filter_by_lifecycle,
    is_at_risk,
)
from orders.services.meal_off import CUTOFF_PASSED_NOTE
from user_management.models import CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


DHAKA = ZoneInfo('Asia/Dhaka')
TODAY = date(2026, 8, 10)


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _aware(d: date, hour: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0, tzinfo=DHAKA)


@override_settings(MEDIA_ROOT='test_media')
class CustomerLifecycleTestCase(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.meal = MealCategory.objects.create(
            meal_name='Lifecycle Plan',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('lifecycle.jpg'),
            is_active=True,
            is_subscribable=True,
        )
        self._today_patcher = patch(
            'orders.services.customer_lifecycle.business_today',
            return_value=TODAY,
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._sub_today = patch(
            'orders.services.subscription_service.business_today',
            return_value=TODAY,
        )
        self._sub_today.start()
        self.addCleanup(self._sub_today.stop)

    def _customer(self, suffix: str) -> CustomerProfile:
        user = User.objects.create_user(
            username=f'lc_{suffix}',
            email=f'lc_{suffix}@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        user.groups.add(self.group)
        return CustomerProfile.objects.create(
            user=user,
            phone=f'171200{suffix[-4:].zfill(4)}'[:11],
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

    def _subscribe(
        self,
        customer: CustomerProfile,
        *,
        started_on: date | None = None,
        status: str = CustomerSubscription.Status.ACTIVE,
        cancel_effective_on: date | None = None,
        cancelled_at: datetime | None = None,
        meal_period: str = 'both',
        quantity: int = 1,
    ) -> CustomerSubscription:
        sub = CustomerSubscription.objects.create(
            customer=customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_period_snapshot=meal_period,
            quantity=quantity,
            status=status,
            started_on=started_on or TODAY - timedelta(days=30),
            cancel_effective_on=cancel_effective_on,
            cancelled_at=cancelled_at,
            cancel_source=(
                CustomerSubscription.CancelSource.CUSTOMER
                if status == CustomerSubscription.Status.CANCELLED
                else None
            ),
        )
        return sub

    def test_never_subscribed(self):
        customer = self._customer('never')
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_NEVER_SUBSCRIBED,
        )

    def test_unsubscribed(self):
        customer = self._customer('unsub')
        self._subscribe(
            customer,
            status=CustomerSubscription.Status.CANCELLED,
            cancel_effective_on=TODAY - timedelta(days=5),
            cancelled_at=_aware(TODAY - timedelta(days=5)),
        )
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_UNSUBSCRIBED,
        )

    def test_churn_date_prefers_cancel_effective_on(self):
        customer = self._customer('churn')
        sub = self._subscribe(
            customer,
            status=CustomerSubscription.Status.CANCELLED,
            cancel_effective_on=date(2026, 8, 1),
            cancelled_at=_aware(date(2026, 7, 28)),
        )
        self.assertEqual(churn_date_for_subscription(sub), date(2026, 8, 1))

    def test_churn_date_falls_back_to_cancelled_at_dhaka(self):
        customer = self._customer('churn2')
        # 2026-08-01 01:30 UTC == 2026-08-01 07:30 Dhaka
        cancelled_at = datetime(2026, 8, 1, 1, 30, tzinfo=ZoneInfo('UTC'))
        sub = self._subscribe(
            customer,
            status=CustomerSubscription.Status.CANCELLED,
            cancel_effective_on=None,
            cancelled_at=cancelled_at,
        )
        self.assertEqual(churn_date_for_subscription(sub), date(2026, 8, 1))

    def test_active(self):
        customer = self._customer('active')
        self._subscribe(customer)
        wallet = get_or_create_wallet(customer)
        credit_wallet(wallet, Decimal('5000.00'))
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_ACTIVE,
        )

    def test_won_back(self):
        customer = self._customer('won')
        self._subscribe(
            customer,
            status=CustomerSubscription.Status.CANCELLED,
            started_on=TODAY - timedelta(days=60),
            cancel_effective_on=TODAY - timedelta(days=20),
            cancelled_at=_aware(TODAY - timedelta(days=20)),
        )
        self._subscribe(customer, started_on=TODAY - timedelta(days=10))
        wallet = get_or_create_wallet(customer)
        credit_wallet(wallet, Decimal('5000.00'))
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_WON_BACK,
        )

    def test_at_risk_takes_precedence_over_won_back(self):
        customer = self._customer('riskwb')
        self._subscribe(
            customer,
            status=CustomerSubscription.Status.CANCELLED,
            started_on=TODAY - timedelta(days=60),
            cancel_effective_on=TODAY - timedelta(days=20),
            cancelled_at=_aware(TODAY - timedelta(days=20)),
        )
        self._subscribe(customer, started_on=TODAY - timedelta(days=10))
        customer.meal_service_blocked_low_balance = True
        customer.meal_service_blocked_at = _aware(TODAY - timedelta(days=4))
        customer.save(
            update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at']
        )
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_AT_RISK,
        )

    def test_at_risk_low_balance_silent_churn(self):
        customer = self._customer('block')
        self._subscribe(customer)
        customer.meal_service_blocked_low_balance = True
        customer.meal_service_blocked_at = _aware(TODAY - timedelta(days=3))
        customer.save(
            update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at']
        )
        self.assertGreaterEqual(count_low_balance_blocked_days(customer, today=TODAY), 3)
        self.assertTrue(is_at_risk(customer, today=TODAY))
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_AT_RISK,
        )

    def test_at_risk_frequent_meal_offs(self):
        customer = self._customer('offs')
        sub = self._subscribe(customer)
        wallet = get_or_create_wallet(customer)
        credit_wallet(wallet, Decimal('5000.00'))
        for i in range(5):
            OrderDelivery.objects.create(
                subscription=sub,
                service_date=TODAY - timedelta(days=i),
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                status=OrderDelivery.DeliveryStatus.SKIPPED,
                skip_source=OrderDelivery.SkipSource.CUSTOMER,
            )
        self.assertEqual(count_meal_off_days(customer, today=TODAY), 5)
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_AT_RISK,
        )

    def test_at_risk_wallet_below_one_day_cost(self):
        customer = self._customer('wallet')
        sub = self._subscribe(customer)
        one_day = estimate_one_day_meal_cost(sub)
        self.assertIsNotNone(one_day)
        self.assertGreater(one_day, Decimal('0'))
        wallet = get_or_create_wallet(customer)
        # Leave balance strictly below one-day cost
        credit_wallet(wallet, max(one_day - Decimal('1.00'), Decimal('0.01')))
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_AT_RISK,
        )

    def test_blocked_two_days_not_at_risk_without_other_signals(self):
        customer = self._customer('short')
        self._subscribe(customer)
        wallet = get_or_create_wallet(customer)
        credit_wallet(wallet, Decimal('5000.00'))
        customer.meal_service_blocked_low_balance = True
        customer.meal_service_blocked_at = _aware(TODAY - timedelta(days=1))
        customer.save(
            update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at']
        )
        self.assertEqual(count_low_balance_blocked_days(customer, today=TODAY), 2)
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_ACTIVE,
        )

    def test_cutoff_passed_skips_count_toward_blocked_days(self):
        customer = self._customer('cutoff')
        sub = self._subscribe(customer)
        wallet = get_or_create_wallet(customer)
        credit_wallet(wallet, Decimal('5000.00'))
        for i in range(3):
            OrderDelivery.objects.create(
                subscription=sub,
                service_date=TODAY - timedelta(days=i),
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                status=OrderDelivery.DeliveryStatus.SKIPPED,
                skip_source=OrderDelivery.SkipSource.SYSTEM,
                note=CUTOFF_PASSED_NOTE,
            )
        self.assertGreaterEqual(count_low_balance_blocked_days(customer, today=TODAY), 3)
        self.assertEqual(
            classify_customer_lifecycle(customer, today=TODAY),
            LIFECYCLE_AT_RISK,
        )

    def test_annotate_lifecycle_matches_python_classifier(self):
        never_c = self._customer('a_never')
        unsub_c = self._customer('a_unsub')
        self._subscribe(
            unsub_c,
            status=CustomerSubscription.Status.CANCELLED,
            cancel_effective_on=TODAY - timedelta(days=2),
            cancelled_at=_aware(TODAY - timedelta(days=2)),
        )
        active_c = self._customer('a_active')
        self._subscribe(active_c)
        credit_wallet(get_or_create_wallet(active_c), Decimal('5000.00'))

        qs = annotate_lifecycle(
            CustomerProfile.objects.filter(
                pk__in=[never_c.pk, unsub_c.pk, active_c.pk]
            ),
            today=TODAY,
        )
        by_id = {row.pk: row.lifecycle for row in qs}
        self.assertEqual(by_id[never_c.pk], LIFECYCLE_NEVER_SUBSCRIBED)
        self.assertEqual(by_id[unsub_c.pk], LIFECYCLE_UNSUBSCRIBED)
        self.assertEqual(by_id[active_c.pk], LIFECYCLE_ACTIVE)

        filtered = filter_by_lifecycle(
            CustomerProfile.objects.all(),
            LIFECYCLE_UNSUBSCRIBED,
            today=TODAY,
        )
        self.assertIn(unsub_c.pk, set(filtered.values_list('pk', flat=True)))
        self.assertNotIn(active_c.pk, set(filtered.values_list('pk', flat=True)))
