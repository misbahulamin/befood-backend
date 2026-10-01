"""Cutoff-aware canonical subscription cancel unit tests."""

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
from orders.services.subscription_service import cancel_subscription, subscribe_customer
from user_management.models import CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class SubscriptionCancelCutoffTests(TestCase):
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

        wallet_settings = OrderWalletSettings.load()
        wallet_settings.min_wallet_balance_to_order = Decimal('0.00')
        wallet_settings.save()

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='cancel_cutoff',
            email='cancel_cutoff@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.user.groups.add(customer_group)
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712999001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.plan = MealCategory.objects.create(
            meal_name='Cutoff Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('cutoff-sub.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        credit_wallet(get_or_create_wallet(self.profile), Decimal('500.00'))
        self.subscription = subscribe_customer(self.profile, self.plan, today=self.today)

    def _slot(self, service_date, meal_period):
        return self.subscription.deliveries.get(
            service_date=service_date,
            meal_period=meal_period,
        )

    def test_cancel_before_dinner_keeps_lunch_skips_dinner(self):
        # After lunch (02:00), before dinner (16:00).
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=self.tz)
        cancel_subscription(self.subscription, now=now, cancel_source='customer')
        lunch = self._slot(self.today, 'lunch')
        dinner = self._slot(self.today, 'dinner')
        lunch.refresh_from_db()
        dinner.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(dinner.skip_source, OrderDelivery.SkipSource.SYSTEM)

    def test_cancel_after_both_cutoffs_preserves_same_day(self):
        now = datetime(2026, 7, 10, 20, 0, 0, tzinfo=self.tz)
        cancel_subscription(self.subscription, now=now)
        for period in ('lunch', 'dinner'):
            slot = self._slot(self.today, period)
            slot.refresh_from_db()
            self.assertEqual(slot.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertTrue(
            self.subscription.deliveries.filter(
                service_date__gt=self.today,
                status=OrderDelivery.DeliveryStatus.SKIPPED,
            ).exists()
        )

    def test_exact_dinner_cutoff_still_cancellable(self):
        now = datetime(2026, 7, 10, 16, 0, 0, tzinfo=self.tz)
        cancel_subscription(self.subscription, now=now)
        dinner = self._slot(self.today, 'dinner')
        dinner.refresh_from_db()
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SKIPPED)

    def test_future_dates_are_skipped(self):
        now = datetime(2026, 7, 10, 20, 0, 0, tzinfo=self.tz)
        future_ids = list(
            self.subscription.deliveries.filter(
                service_date__gt=self.today,
                status=OrderDelivery.DeliveryStatus.SCHEDULED,
            ).values_list('pk', flat=True)
        )
        self.assertGreater(len(future_ids), 0)
        cancel_subscription(self.subscription, now=now)
        for pk in future_ids:
            row = OrderDelivery.objects.get(pk=pk)
            self.assertEqual(row.status, OrderDelivery.DeliveryStatus.SKIPPED)
            self.assertEqual(row.skip_source, OrderDelivery.SkipSource.SYSTEM)

    def test_delivered_untouched(self):
        lunch = self._slot(self.today, 'lunch')
        lunch.status = OrderDelivery.DeliveryStatus.DELIVERED
        lunch.payment_status = OrderDelivery.PaymentStatus.CHARGED
        lunch.charged_amount = Decimal('80.00')
        lunch.save(
            update_fields=['status', 'payment_status', 'charged_amount', 'updated_at']
        )
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=self.tz)
        cancel_subscription(self.subscription, now=now)
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(lunch.charged_amount, Decimal('80.00'))

    def test_repeat_cancel_idempotent(self):
        now = datetime(2026, 7, 10, 12, 0, 0, tzinfo=self.tz)
        first = cancel_subscription(
            self.subscription,
            now=now,
            cancelled_by=self.user,
            cancel_source='customer',
        )
        dinner = self._slot(self.today, 'dinner')
        dinner.refresh_from_db()
        marked_at = dinner.marked_at
        second = cancel_subscription(
            self.subscription,
            now=now,
            cancelled_by=self.user,
            cancel_source='admin',
        )
        self.assertEqual(first.pk, second.pk)
        dinner.refresh_from_db()
        self.assertEqual(dinner.marked_at, marked_at)
        self.assertEqual(second.cancel_source, CustomerSubscription.CancelSource.CUSTOMER)
