"""Subscription slot creation must respect meal-off cutoffs (Asia/Dhaka)."""

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
from orders.models import MealOffSettings, OrderDelivery, OrderWalletSettings
from orders.services.auto_meal_delivery import eligible_delivery_queryset
from orders.services.meal_off import CUTOFF_PASSED_NOTE
from orders.services.subscription_service import (
    ensure_subscription_deliveries,
    subscribe_customer,
)
from user_management.models import CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class SubscriptionMealCutoffTests(TestCase):
    def setUp(self):
        self.tz = ZoneInfo('Asia/Dhaka')
        self.service_date = date(2026, 9, 8)
        settings_obj = MealOffSettings.load()
        settings_obj.timezone = 'Asia/Dhaka'
        settings_obj.lunch_off_time = time(2, 0)
        settings_obj.dinner_off_time = time(16, 0)
        settings_obj.save()

        wallet_settings = OrderWalletSettings.load()
        wallet_settings.min_wallet_balance_to_order = Decimal('0.00')
        wallet_settings.save()

        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=self.service_date,
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='cutoff_customer',
            email='cutoff@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.user,
            phone='1712555099',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.plan = MealCategory.objects.create(
            meal_name='Cutoff Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('cutoff-pkg.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        wallet = get_or_create_wallet(self.customer)
        credit_wallet(wallet, Decimal('500.00'))

    def _subscribe_at(self, hour, minute, second=0):
        now = datetime(
            self.service_date.year,
            self.service_date.month,
            self.service_date.day,
            hour,
            minute,
            second,
            tzinfo=self.tz,
        )
        with patch(
            'orders.services.subscription_service.meal_off_business_now',
            return_value=now,
        ):
            return subscribe_customer(
                self.customer,
                self.plan,
                today=self.service_date,
            )

    def _today_slot(self, subscription, meal_period):
        return subscription.deliveries.get(
            service_date=self.service_date,
            meal_period=meal_period,
        )

    def test_subscribe_before_lunch_cutoff_keeps_lunch_scheduled(self):
        subscription = self._subscribe_at(1, 59)
        lunch = self._today_slot(subscription, 'lunch')
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertIsNone(lunch.skip_source)
        self.assertIn(
            lunch,
            list(eligible_delivery_queryset(self.service_date, 'lunch')),
        )

    def test_subscribe_after_lunch_cutoff_skips_lunch_no_auto_delivery(self):
        subscription = self._subscribe_at(2, 1)
        lunch = self._today_slot(subscription, 'lunch')
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(lunch.skip_source, OrderDelivery.SkipSource.SYSTEM)
        self.assertEqual(lunch.note, CUTOFF_PASSED_NOTE)
        self.assertIsNotNone(lunch.marked_at)
        self.assertNotIn(
            lunch,
            list(eligible_delivery_queryset(self.service_date, 'lunch')),
        )
        self.assertEqual(
            OrderDelivery.objects.filter(
                pk=lunch.pk,
                payment_status=OrderDelivery.PaymentStatus.CHARGED,
            ).count(),
            0,
        )

    def test_subscribe_before_dinner_cutoff_keeps_dinner_scheduled(self):
        subscription = self._subscribe_at(15, 59)
        dinner = self._today_slot(subscription, 'dinner')
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_subscribe_after_dinner_cutoff_skips_dinner(self):
        subscription = self._subscribe_at(16, 1)
        dinner = self._today_slot(subscription, 'dinner')
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(dinner.skip_source, OrderDelivery.SkipSource.SYSTEM)
        self.assertEqual(dinner.note, CUTOFF_PASSED_NOTE)

    def test_subscribe_at_0300_skips_lunch_keeps_dinner(self):
        subscription = self._subscribe_at(3, 0)
        lunch = self._today_slot(subscription, 'lunch')
        dinner = self._today_slot(subscription, 'dinner')
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(lunch.note, CUTOFF_PASSED_NOTE)
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_subscribe_after_both_cutoffs_skips_lunch_and_dinner(self):
        subscription = self._subscribe_at(17, 0)
        lunch = self._today_slot(subscription, 'lunch')
        dinner = self._today_slot(subscription, 'dinner')
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SKIPPED)

    def test_future_day_slots_remain_scheduled_after_today_cutoff(self):
        subscription = self._subscribe_at(3, 0)
        tomorrow = self.service_date.fromordinal(self.service_date.toordinal() + 1)
        tomorrow_lunch = subscription.deliveries.get(
            service_date=tomorrow,
            meal_period='lunch',
        )
        self.assertEqual(tomorrow_lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_ensure_does_not_mutate_existing_scheduled_after_cutoff(self):
        subscription = self._subscribe_at(1, 59)
        lunch = self._today_slot(subscription, 'lunch')
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        after = datetime(2026, 9, 8, 3, 0, tzinfo=self.tz)
        ensure_subscription_deliveries(
            subscription,
            today=self.service_date,
            now=after,
        )
        lunch.refresh_from_db()
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertEqual(
            subscription.deliveries.filter(
                service_date=self.service_date,
                meal_period='lunch',
            ).count(),
            1,
        )

    def test_cutoff_uses_asia_dhaka_when_now_is_utc(self):
        # 02:01 Dhaka == 20:01 previous calendar day UTC
        utc_now = datetime(2026, 9, 7, 20, 1, 0, tzinfo=ZoneInfo('UTC'))
        with patch(
            'orders.services.subscription_service.meal_off_business_now',
            return_value=utc_now,
        ):
            subscription = subscribe_customer(
                self.customer,
                self.plan,
                today=self.service_date,
            )
        lunch = self._today_slot(subscription, 'lunch')
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(lunch.note, CUTOFF_PASSED_NOTE)
        dinner = self._today_slot(subscription, 'dinner')
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SCHEDULED)
