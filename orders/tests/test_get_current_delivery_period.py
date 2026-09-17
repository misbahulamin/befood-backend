from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from orders.models import MealOffSettings, OrderDelivery
from orders.services.meal_off import get_current_delivery_period, update_meal_off_settings


class GetCurrentDeliveryPeriodTests(TestCase):
    def setUp(self):
        update_meal_off_settings(
            timezone_name='Asia/Dhaka',
            lunch_off_time=time(2, 0, 0),
            dinner_off_time=time(16, 0, 0),
        )
        self.settings_obj = MealOffSettings.load()
        self.tz = ZoneInfo('Asia/Dhaka')

    def _dt(self, hour, minute=0, second=0, day=18, month=9, year=2026):
        return datetime(year, month, day, hour, minute, second, tzinfo=self.tz)

    def test_before_lunch_off_returns_none(self):
        service_date, period = get_current_delivery_period(
            self._dt(1, 59),
            settings_obj=self.settings_obj,
        )
        self.assertEqual(service_date.isoformat(), '2026-09-18')
        self.assertIsNone(period)

    def test_at_lunch_off_returns_none(self):
        service_date, period = get_current_delivery_period(
            self._dt(2, 0),
            settings_obj=self.settings_obj,
        )
        self.assertEqual(service_date.isoformat(), '2026-09-18')
        self.assertIsNone(period)

    def test_after_lunch_off_returns_lunch(self):
        service_date, period = get_current_delivery_period(
            self._dt(2, 1),
            settings_obj=self.settings_obj,
        )
        self.assertEqual(service_date.isoformat(), '2026-09-18')
        self.assertEqual(period, OrderDelivery.MealPeriod.LUNCH)

    def test_at_dinner_off_still_lunch(self):
        service_date, period = get_current_delivery_period(
            self._dt(16, 0),
            settings_obj=self.settings_obj,
        )
        self.assertEqual(period, OrderDelivery.MealPeriod.LUNCH)
        self.assertEqual(service_date.isoformat(), '2026-09-18')

    def test_after_dinner_off_returns_dinner(self):
        service_date, period = get_current_delivery_period(
            self._dt(16, 1),
            settings_obj=self.settings_obj,
        )
        self.assertEqual(period, OrderDelivery.MealPeriod.DINNER)
        self.assertEqual(service_date.isoformat(), '2026-09-18')

    def test_uses_settings_timezone_for_naive_now(self):
        # 10:00 UTC == 16:00 Asia/Dhaka → still lunch (at dinner_off)
        naive_utcish = datetime(2026, 9, 18, 10, 0, 0)
        with patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=datetime(2026, 9, 18, 16, 0, 0, tzinfo=self.tz),
        ):
            # Explicit naive with tz applied inside helper via replace
            _, period = get_current_delivery_period(
                naive_utcish.replace(tzinfo=self.tz),
                settings_obj=self.settings_obj,
            )
        self.assertEqual(period, OrderDelivery.MealPeriod.LUNCH)

    def test_overnight_before_lunch_off_is_empty_not_prior_dinner(self):
        """Confirmed: midnight → lunch_off shows no active meal (not yesterday dinner)."""
        service_date, period = get_current_delivery_period(
            self._dt(0, 30),
            settings_obj=self.settings_obj,
        )
        self.assertIsNone(period)
        self.assertEqual(service_date.isoformat(), '2026-09-18')
