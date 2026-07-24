from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from meals.models import MealCategory
from meals.services.pricing import (
    calculate_per_meal_price,
    expected_servings,
    periods_per_day,
)
from orders.models import Order
from orders.services.order_delivery import expected_delivery_count, generate_order_deliveries
from user_management.models import CustomerProfile

def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class ServingCountHelperTests(SimpleTestCase):
    def test_periods_per_day(self):
        self.assertEqual(periods_per_day('lunch'), 1)
        self.assertEqual(periods_per_day('dinner'), 1)
        self.assertEqual(periods_per_day('both'), 2)

    def test_daily_lunch_and_both(self):
        self.assertEqual(expected_servings('daily', 'lunch', 2026, 4), 1)
        self.assertEqual(expected_servings('daily', 'both', 2026, 4), 2)

    def test_monthly_dinner_and_both(self):
        self.assertEqual(expected_servings('monthly', 'dinner', 2026, 4), 30)
        self.assertEqual(expected_servings('monthly', 'both', 2026, 1), 62)

    def test_leap_february_monthly_both(self):
        self.assertEqual(expected_servings('monthly', 'both', 2028, 2), 58)

    def test_weekly_lunch_and_both(self):
        self.assertEqual(expected_servings('weekly', 'lunch', 2026, 7), 7)
        self.assertEqual(expected_servings('weekly', 'both', 2026, 7), 14)

    def test_per_meal_price_monthly_dinner(self):
        price = calculate_per_meal_price(
            Decimal('3000.00'),
            'monthly',
            'dinner',
            reference_date=date(2026, 4, 10),
        )
        self.assertEqual(price, Decimal('100.00'))

    def test_per_meal_price_daily_both(self):
        price = calculate_per_meal_price(
            Decimal('200.00'),
            'daily',
            'both',
            reference_date=date(2026, 4, 10),
        )
        self.assertEqual(price, Decimal('100.00'))


@override_settings(MEDIA_ROOT='test_media')
class PeriodAwareDeliveryTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username='period-customer',
            email='period-customer@example.com',
            password='StrongPassword123',
        )
        self.customer = CustomerProfile.objects.create(
            user=user,
            phone='1711999888',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

    def _order(self, meal_type, meal_period, start, end, order_month, service_days):
        meal = MealCategory.objects.create(
            meal_name=f'{meal_type}-{meal_period}',
            total_price=Decimal('100.00'),
            meal_type=meal_type,
            meal_period=meal_period,
            meal_thumbnail=make_test_image(f'{meal_type}-{meal_period}.jpg'),
        )
        return Order.objects.create(
            customer=self.customer,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_type_snapshot=meal_type,
            meal_period_snapshot=meal_period,
            total_price_snapshot=meal.total_price,
            per_meal_price_snapshot=Decimal('10.00'),
            order_start_date=start,
            order_end_date=end,
            service_days_count=service_days,
            order_month=order_month,
        )

    def test_daily_lunch_one_slot(self):
        order = self._order('daily', 'lunch', date(2026, 7, 10), date(2026, 7, 10), '2026-07', 1)
        slots = generate_order_deliveries(order)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].meal_period, 'lunch')
        self.assertEqual(expected_delivery_count(order), 1)

    def test_daily_both_two_slots(self):
        order = self._order('daily', 'both', date(2026, 7, 10), date(2026, 7, 10), '2026-07', 1)
        slots = generate_order_deliveries(order)
        self.assertEqual(len(slots), 2)
        self.assertEqual({s.meal_period for s in slots}, {'lunch', 'dinner'})
        self.assertEqual(expected_delivery_count(order), 2)

    def test_monthly_dinner_thirty_in_april(self):
        order = self._order('monthly', 'dinner', date(2026, 4, 1), date(2026, 4, 30), '2026-04', 30)
        slots = generate_order_deliveries(order)
        self.assertEqual(len(slots), 30)
        self.assertTrue(all(s.meal_period == 'dinner' for s in slots))
        self.assertEqual(expected_delivery_count(order), 30)

    def test_monthly_both_sixty_two_in_january(self):
        order = self._order('monthly', 'both', date(2026, 1, 1), date(2026, 1, 31), '2026-01', 31)
        slots = generate_order_deliveries(order)
        self.assertEqual(len(slots), 62)
        self.assertEqual(expected_delivery_count(order), 62)

    def test_weekly_lunch_seven_and_both_fourteen(self):
        lunch = self._order('weekly', 'lunch', date(2026, 7, 10), date(2026, 7, 16), '2026-07', 7)
        both = self._order('weekly', 'both', date(2026, 8, 10), date(2026, 8, 16), '2026-08', 7)
        self.assertEqual(len(generate_order_deliveries(lunch)), 7)
        self.assertEqual(expected_delivery_count(lunch), 7)
        self.assertEqual(len(generate_order_deliveries(both)), 14)
        self.assertEqual(expected_delivery_count(both), 14)
