from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import (
    Ingredient,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MealCyclePlanLine,
    MonthlyMenuSchedule,
)
from meals.services.cycle_calculations import finalize_plan
from meals.services.menu_schedule import (
    expected_slot_keys,
    publish_schedule,
    replace_schedule_assignments,
)
from meals.services.today_menu import build_today_menu_for_customer
from orders.models import Order
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class CustomerPackageMenuAPITestCase(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='pkg-menu-admin',
            email='pkg-menu-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='pkg-menu-customer',
            email='pkg-menu-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345688',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.meal = MealCategory.objects.create(
            meal_name='Regular Package',
            total_price=Decimal('3000.00'),
            meal_type='monthly',
            meal_period='both',
            meal_thumbnail=make_test_image('regular.jpg'),
        )
        self.chicken = Ingredient.objects.create(
            name='Chicken',
            price_per_kg=Decimal('130.00'),
            customers_per_kg=Decimal('10.00'),
            product_role=Ingredient.ProductRole.MAIN,
        )
        self.beef = Ingredient.objects.create(
            name='Beef',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
            product_role=Ingredient.ProductRole.MAIN,
        )
        self.rice = Ingredient.objects.create(
            name='Rice',
            price_per_kg=Decimal('70.00'),
            customers_per_kg=Decimal('7.00'),
            product_role=Ingredient.ProductRole.STAPLE,
        )

        self.url = reverse('meals:my-package-menu')
        self.today_url = reverse('meals:today-menu')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _finalize_plan(self, year, month, chicken_count, beef_count):
        cycle, _ = MealCycle.objects.get_or_create(year=year, month=month)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=self.meal)
        total = cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=plan, ingredient=self.chicken, servings_count=chicken_count
        )
        MealCyclePlanLine.objects.create(
            plan=plan, ingredient=self.beef, servings_count=beef_count
        )
        MealCyclePlanLine.objects.create(
            plan=plan, ingredient=self.rice, servings_count=total
        )
        assert chicken_count + beef_count == total
        return finalize_plan(plan)

    def _full_main_assignments(self, plan, chicken_slots, beef_slots):
        keys = expected_slot_keys(plan.cycle.year, plan.cycle.month)
        chicken_set = set(chicken_slots)
        beef_set = set(beef_slots)
        assignments = []
        for key in keys:
            if key in chicken_set:
                main_id = self.chicken.id
            elif key in beef_set:
                main_id = self.beef.id
            else:
                raise AssertionError(f'Uncovered slot {key}')
            assignments.append(
                {
                    'service_date': key[0].isoformat(),
                    'meal_period': key[1],
                    'ingredient_ids': [main_id, self.rice.id],
                }
            )
        return assignments

    def _create_published_schedule(self, year=2026, month=7):
        plan = self._finalize_plan(year, month, chicken_count=20, beef_count=42)
        keys = expected_slot_keys(year, month)
        chicken_keys, beef_keys = keys[:20], keys[20:]
        assignments = self._full_main_assignments(plan, chicken_keys, beef_keys)
        schedule = MonthlyMenuSchedule.objects.create(plan=plan)
        replace_schedule_assignments(schedule, assignments)
        return publish_schedule(schedule)

    def _create_draft_schedule(self, year=2026, month=7):
        plan = self._finalize_plan(year, month, chicken_count=20, beef_count=42)
        return MonthlyMenuSchedule.objects.create(plan=plan)

    def _create_order(self, year=2026, month=7):
        return Order.objects.create(
            customer=self.customer_profile,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_type_snapshot=self.meal.meal_type,
            meal_period_snapshot=self.meal.meal_period,
            total_price_snapshot=self.meal.total_price,
            per_meal_price_snapshot=Decimal('50.00'),
            order_status=Order.OrderStatus.CONFIRMED,
            order_start_date=date(year, month, 1),
            order_end_date=date(year, month, 28),
            service_days_count=28,
            order_month=f'{year:04d}-{month:02d}',
        )

    def test_verified_customer_gets_full_published_month_menu(self):
        schedule = self._create_published_schedule(2026, 7)
        order = self._create_order(2026, 7)
        expected_days = schedule.slots.count()

        self._auth_customer()
        response = self.client.get(self.url, {'year': 2026, 'month': 7})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['year'], 2026)
        self.assertEqual(response.data['month'], 7)
        self.assertEqual(len(response.data['packages']), 1)
        package = response.data['packages'][0]
        self.assertEqual(package['meal_public_id'], str(self.meal.public_id))
        self.assertEqual(package['meal_name'], 'Regular Package')
        self.assertEqual(package['order_public_id'], str(order.public_id))
        self.assertTrue(package['schedule_published'])
        self.assertEqual(len(package['days']), expected_days)
        self.assertIn('ingredients', package['days'][0])
        self.assertTrue(len(package['days'][0]['ingredients']) >= 1)
        periods = {d['meal_period'] for d in package['days']}
        self.assertEqual(periods, {'lunch', 'dinner'})
        # Ordered by service_date then meal_period (dinner before lunch alphabetically)
        dates = [d['service_date'] for d in package['days']]
        self.assertEqual(dates, sorted(dates))
        first_date_slots = [
            d for d in package['days'] if d['service_date'] == package['days'][0]['service_date']
        ]
        self.assertEqual(
            [d['meal_period'] for d in first_date_slots],
            sorted(d['meal_period'] for d in first_date_slots),
        )

    def test_unpublished_schedule_returns_empty_days(self):
        self._create_draft_schedule(2026, 7)
        order = self._create_order(2026, 7)

        self._auth_customer()
        response = self.client.get(self.url, {'year': 2026, 'month': 7})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['packages']), 1)
        package = response.data['packages'][0]
        self.assertEqual(package['order_public_id'], str(order.public_id))
        self.assertFalse(package['schedule_published'])
        self.assertEqual(package['days'], [])

    def test_no_active_order_returns_empty_packages(self):
        self._create_published_schedule(2026, 7)

        self._auth_customer()
        response = self.client.get(self.url, {'year': 2026, 'month': 7})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['packages'], [])

    def test_unauthenticated_returns_401(self):
        response = self.client.get(self.url, {'year': 2026, 'month': 7})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_year_month_query_returns_400(self):
        self._auth_customer()

        only_year = self.client.get(self.url, {'year': 2026})
        self.assertEqual(only_year.status_code, status.HTTP_400_BAD_REQUEST)

        only_month = self.client.get(self.url, {'month': 7})
        self.assertEqual(only_month.status_code, status.HTTP_400_BAD_REQUEST)

        bad_month = self.client.get(self.url, {'year': 2026, 'month': 13})
        self.assertEqual(bad_month.status_code, status.HTTP_400_BAD_REQUEST)

    def test_today_menu_reveal_behavior_unchanged(self):
        self._create_published_schedule(2026, 7)
        self._create_order(2026, 7)
        tz = ZoneInfo('Asia/Dhaka')

        before_lunch = datetime(2026, 7, 22, 7, 0, tzinfo=tz)
        payload = build_today_menu_for_customer(self.customer_profile, now=before_lunch)
        self.assertEqual(payload['visible_periods'], [])
        self.assertEqual(payload['packages'][0]['periods'], [])

        after_dinner = datetime(2026, 7, 22, 17, 0, tzinfo=tz)
        payload_dinner = build_today_menu_for_customer(
            self.customer_profile, now=after_dinner
        )
        self.assertEqual(payload_dinner['visible_periods'], ['lunch', 'dinner'])
        self.assertEqual(len(payload_dinner['packages'][0]['periods']), 2)

        # Full package menu still returns all days without reveal gating
        self._auth_customer()
        full = self.client.get(self.url, {'year': 2026, 'month': 7})
        self.assertEqual(full.status_code, status.HTTP_200_OK)
        self.assertGreater(len(full.data['packages'][0]['days']), 2)
