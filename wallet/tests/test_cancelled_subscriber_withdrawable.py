"""Cancelled-subscriber withdrawable / finalized meal liability tests."""

from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from meals.models import MealCategory
from orders.models import CustomerSubscription, MealOffSettings, OrderDelivery, OrderWalletSettings
from orders.services.meal_payment import (
    compute_finalized_meal_liability,
    estimate_delivery_charge,
)
from orders.services.subscription_service import cancel_subscription, subscribe_customer
from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot
from user_management.models import CustomerProfile
from wallet.services.funding import request_withdraw
from wallet.services.ledger import InsufficientFundsError, credit_wallet, get_or_create_wallet
from wallet.services.withdrawable import compute_maximum_withdrawable


def make_test_image(name='meal.jpg', size=(100, 100), color='green'):
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _set_meal_stop(amount: Decimal) -> None:
    settings_obj = OrderWalletSettings.load()
    settings_obj.meal_stop_threshold = amount
    settings_obj.min_wallet_balance_to_order = Decimal('0.00')
    settings_obj.save()


@override_settings(MEDIA_ROOT='test_media', MEAL_DELIVERY_WALLET_CHARGE_ENABLED=True)
class CancelledSubscriberWithdrawableTests(TestCase):
    def setUp(self):
        self.today = date(2026, 7, 10)
        self.tz = ZoneInfo('Asia/Dhaka')
        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=self.today,
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        settings_obj = MealOffSettings.load()
        settings_obj.timezone = 'Asia/Dhaka'
        settings_obj.lunch_off_time = time(2, 0, 0)
        settings_obj.dinner_off_time = time(16, 0, 0)
        settings_obj.save()
        _set_meal_stop(Decimal('100.00'))

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='liability_cust',
            email='liability@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.user.groups.add(customer_group)
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712888001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.plan = MealCategory.objects.create(
            meal_name='Liability Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('liability.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        self.wallet = get_or_create_wallet(self.profile)
        credit_wallet(self.wallet, Decimal('300.00'))
        self.subscription = subscribe_customer(self.profile, self.plan, today=self.today)
        ensure_priced_delivery_slot(
            self.plan, self.today, OrderDelivery.MealPeriod.LUNCH, Decimal('80.00')
        )
        ensure_priced_delivery_slot(
            self.plan, self.today, OrderDelivery.MealPeriod.DINNER, Decimal('80.00')
        )

    def test_active_subscriber_keeps_meal_stop_floor(self):
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.withdrawable_balance, Decimal('200.00'))
        self.assertEqual(
            compute_maximum_withdrawable(
                Decimal('300.00'),
                Decimal('100.00'),
                has_active_subscription=True,
            ),
            Decimal('200.00'),
        )

    def test_after_cancel_with_preserved_dinner_liability(self):
        # Lunch past cutoff preserved; dinner still cancellable → skipped.
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=self.tz)
        with patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=now,
        ):
            cancel_subscription(self.subscription, now=now)
            self.wallet.refresh_from_db()
            self.assertEqual(
                compute_finalized_meal_liability(self.profile, now=now),
                Decimal('80.00'),
            )
            self.assertEqual(self.wallet.withdrawable_balance, Decimal('220.00'))

    def test_after_cancel_no_preserved_full_recharge(self):
        # Before lunch cutoff: both today slots cancelled; no liability.
        now = datetime(2026, 7, 10, 1, 0, 0, tzinfo=self.tz)
        with patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=now,
        ):
            cancel_subscription(self.subscription, now=now)
            self.wallet.refresh_from_db()
            self.assertEqual(compute_finalized_meal_liability(self.profile, now=now), Decimal('0.00'))
            self.assertEqual(self.wallet.withdrawable_balance, Decimal('300.00'))

    def test_withdraw_validation_matches_withdrawable(self):
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=self.tz)
        with patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=now,
        ):
            cancel_subscription(self.subscription, now=now)
            self.wallet.refresh_from_db()
            with self.assertRaises(InsufficientFundsError):
                request_withdraw(self.profile, Decimal('220.01'))
            _, txn, _ = request_withdraw(self.profile, Decimal('220.00'))
            self.assertEqual(txn.amount, Decimal('220.00'))
            self.wallet.refresh_from_db()
            self.assertEqual(self.wallet.recharge_balance, Decimal('80.00'))

    def test_liability_clears_after_preserved_meal_charged(self):
        from orders.services.meal_payment import charge_delivered_meal

        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=self.tz)
        with patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=now,
        ):
            cancel_subscription(self.subscription, now=now)
            lunch = self.subscription.deliveries.get(
                service_date=self.today,
                meal_period='lunch',
            )
            lunch.status = OrderDelivery.DeliveryStatus.DELIVERED
            lunch.save(update_fields=['status', 'updated_at'])
            charge_delivered_meal(lunch)
            self.wallet.refresh_from_db()
            self.assertEqual(self.wallet.recharge_balance, Decimal('220.00'))
            self.assertEqual(
                compute_finalized_meal_liability(self.profile, now=now),
                Decimal('0.00'),
            )
            self.assertEqual(self.wallet.withdrawable_balance, Decimal('220.00'))

    def test_estimate_matches_charge_amount_source(self):
        dinner = self.subscription.deliveries.get(
            service_date=self.today,
            meal_period='dinner',
        )
        self.assertEqual(estimate_delivery_charge(dinner), Decimal('80.00'))
