from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import (
    Ingredient,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from orders.models import MealDemandSnapshot, MealOffSettings, Order, OrderDelivery
from orders.services.meal_demand import (
    CONFIRMATION_CONFIRMED,
    CONFIRMATION_ESTIMATED,
    confirmation_status,
    get_demand,
    get_ingredient_requirements,
    resolve_default_kitchen_slot,
    upsert_demand_snapshots_for_slot,
)
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class MealDemandHelperTests(SimpleTestCase):
    def setUp(self):
        self.settings_obj = MealOffSettings(
            timezone='Asia/Dhaka',
            lunch_off_time=time(23, 59),
            dinner_off_time=time(14, 0),
        )

    def test_confirmation_estimated_before_dinner_deadline(self):
        now = datetime(2026, 8, 5, 13, 59, tzinfo=ZoneInfo('Asia/Dhaka'))
        self.assertEqual(
            confirmation_status(date(2026, 8, 5), 'dinner', now=now, settings_obj=self.settings_obj),
            CONFIRMATION_ESTIMATED,
        )

    def test_confirmation_confirmed_after_dinner_deadline(self):
        now = datetime(2026, 8, 5, 14, 0, 1, tzinfo=ZoneInfo('Asia/Dhaka'))
        self.assertEqual(
            confirmation_status(date(2026, 8, 5), 'dinner', now=now, settings_obj=self.settings_obj),
            CONFIRMATION_CONFIRMED,
        )

    def test_default_kitchen_slot_morning_lunch(self):
        now = datetime(2026, 8, 5, 10, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        service_date, period = resolve_default_kitchen_slot(now, settings_obj=self.settings_obj)
        self.assertEqual(service_date, date(2026, 8, 5))
        self.assertEqual(period, 'lunch')

    def test_default_kitchen_slot_afternoon_dinner(self):
        now = datetime(2026, 8, 5, 15, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        service_date, period = resolve_default_kitchen_slot(now, settings_obj=self.settings_obj)
        self.assertEqual(service_date, date(2026, 8, 5))
        self.assertEqual(period, 'dinner')


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MealDemandServiceTestCase(TestCase):
    def setUp(self):
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.settings_obj = MealOffSettings.load()
        self.settings_obj.timezone = 'Asia/Dhaka'
        self.settings_obj.lunch_off_time = time(23, 59)
        self.settings_obj.dinner_off_time = time(14, 0)
        self.settings_obj.save()

        self.premium = MealCategory.objects.create(
            meal_name='Premium Package',
            total_price=Decimal('4000.00'),
            meal_thumbnail=make_test_image('premium-demand.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.regular = MealCategory.objects.create(
            meal_name='Regular Package',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('regular-demand.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )

        self.rice = Ingredient.objects.create(
            name='Rice Demand',
            price_per_kg=Decimal('80.00'),
            customers_per_kg=Decimal('5.00'),  # 0.2 kg per person
            is_active=True,
        )
        self.spice = Ingredient.objects.create(
            name='Spice Demand',
            cost_per_customer=Decimal('2.00'),
            is_active=True,
        )

        self.service_date = date(2026, 8, 5)
        self._seed_orders_and_menu()

    def _make_customer(self, suffix: str) -> CustomerProfile:
        user = User.objects.create_user(
            username=f'demand_{suffix}',
            email=f'demand_{suffix}@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        user.groups.add(self.customer_group)
        return CustomerProfile.objects.create(
            user=user,
            phone=f'{1000000000 + (abs(hash(suffix)) % 900000000):d}'[:10],
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

    def _create_order_with_dinner(self, customer, meal, *, skipped=False, cancelled=False):
        order = Order.objects.create(
            customer=customer,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_type_snapshot=meal.meal_type,
            meal_period_snapshot=meal.meal_period,
            total_price_snapshot=meal.total_price,
            per_meal_price_snapshot=Decimal('100.00'),
            order_status=(
                Order.OrderStatus.CANCELLED if cancelled else Order.OrderStatus.ACTIVE
            ),
            order_start_date=self.service_date,
            order_end_date=self.service_date,
            service_days_count=1,
            order_month='2026-08',
        )
        OrderDelivery.objects.create(
            order=order,
            service_date=self.service_date,
            meal_period=OrderDelivery.MealPeriod.DINNER,
            status=(
                OrderDelivery.DeliveryStatus.SKIPPED
                if skipped
                else OrderDelivery.DeliveryStatus.SCHEDULED
            ),
            skip_source=OrderDelivery.SkipSource.CUSTOMER if skipped else None,
        )
        return order

    def _seed_orders_and_menu(self):
        # Premium: 3 expected, 1 off → final 2
        for i in range(3):
            self._create_order_with_dinner(
                self._make_customer(f'p{i}'),
                self.premium,
                skipped=(i == 0),
            )
        # Regular: 2 expected, 0 off → final 2
        for i in range(2):
            self._create_order_with_dinner(self._make_customer(f'r{i}'), self.regular)
        # Cancelled order must be ignored
        self._create_order_with_dinner(
            self._make_customer('cx'),
            self.premium,
            cancelled=True,
        )

        cycle = MealCycle.objects.create(year=2026, month=8)
        for meal in (self.premium, self.regular):
            plan = MealCyclePlan.objects.create(
                cycle=cycle,
                meal_category=meal,
                status=MealCyclePlan.Status.FINALIZED,
            )
            schedule = MonthlyMenuSchedule.objects.create(
                plan=plan,
                status=MonthlyMenuSchedule.Status.PUBLISHED,
                published_at=timezone.now(),
            )
            slot = MonthlyMenuSlot.objects.create(
                schedule=schedule,
                service_date=self.service_date,
                meal_period=MonthlyMenuSlot.MealPeriod.DINNER,
            )
            MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=self.rice)
            MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=self.spice)

    def test_get_demand_counts_and_package_isolation(self):
        demand = get_demand(
            self.service_date,
            'dinner',
            settings_obj=self.settings_obj,
        )
        self.assertEqual(demand.expected_meal_count, 5)
        self.assertEqual(demand.meal_off_count, 1)
        self.assertEqual(demand.final_cooking_count, 4)
        by_name = {row.package_name: row for row in demand.packages}
        self.assertEqual(by_name['Premium Package'].expected_meal_count, 3)
        self.assertEqual(by_name['Premium Package'].meal_off_count, 1)
        self.assertEqual(by_name['Premium Package'].final_cooking_count, 2)
        self.assertEqual(by_name['Regular Package'].final_cooking_count, 2)

    def test_package_filter(self):
        demand = get_demand(
            self.service_date,
            'dinner',
            package_public_id=self.premium.public_id,
            settings_obj=self.settings_obj,
        )
        self.assertEqual(demand.expected_meal_count, 3)
        self.assertEqual(len(demand.packages), 1)

    def test_ingredient_scaling_and_flat_only(self):
        demand = get_demand(self.service_date, 'dinner', settings_obj=self.settings_obj)
        ingredients, incomplete = get_ingredient_requirements(demand)
        self.assertFalse(incomplete)
        by_name = {row.name: row for row in ingredients}
        self.assertTrue(by_name['Rice Demand'].quantity_available)
        # 0.2 kg × 4 people (2 premium + 2 regular final)
        self.assertEqual(by_name['Rice Demand'].quantity, Decimal('0.800000'))
        self.assertEqual(by_name['Rice Demand'].kg_per_person, Decimal('0.200000'))
        self.assertEqual(by_name['Rice Demand'].customer_count, 4)
        self.assertEqual(len(by_name['Rice Demand'].package_contributions), 2)
        self.assertFalse(by_name['Spice Demand'].quantity_available)
        self.assertIsNone(by_name['Spice Demand'].quantity)
        self.assertEqual(by_name['Spice Demand'].customer_count, 4)

    def test_item_wise_contributions_shared_and_exclusive(self):
        """Student-style vs Regular-style menus: shared Dal/Rice, exclusive Vegetable/Fish."""
        dal = Ingredient.objects.create(
            name='Dal Shared',
            price_per_kg=Decimal('100.00'),
            customers_per_kg=Decimal('10.00'),
            is_active=True,
        )
        vegetable = Ingredient.objects.create(
            name='Vegetable Only',
            price_per_kg=Decimal('60.00'),
            customers_per_kg=Decimal('5.00'),
            is_active=True,
        )
        fish = Ingredient.objects.create(
            name='Fish Only',
            price_per_kg=Decimal('400.00'),
            customers_per_kg=Decimal('2.00'),
            is_active=True,
        )
        MonthlyMenuSlotItem.objects.filter(slot__service_date=self.service_date).delete()
        premium_slot = MonthlyMenuSlot.objects.get(
            schedule__plan__meal_category=self.premium,
            service_date=self.service_date,
        )
        regular_slot = MonthlyMenuSlot.objects.get(
            schedule__plan__meal_category=self.regular,
            service_date=self.service_date,
        )
        for ingredient in (dal, vegetable, self.rice):
            MonthlyMenuSlotItem.objects.create(slot=premium_slot, ingredient=ingredient)
        for ingredient in (dal, fish, self.rice):
            MonthlyMenuSlotItem.objects.create(slot=regular_slot, ingredient=ingredient)

        demand = get_demand(self.service_date, 'dinner', settings_obj=self.settings_obj)
        ingredients, incomplete = get_ingredient_requirements(demand)
        self.assertFalse(incomplete)
        by_name = {row.name: row for row in ingredients}

        self.assertEqual(by_name['Dal Shared'].customer_count, 4)
        dal_by_pkg = {
            c.package_name: c.customer_count
            for c in by_name['Dal Shared'].package_contributions
        }
        self.assertEqual(dal_by_pkg['Premium Package'], 2)
        self.assertEqual(dal_by_pkg['Regular Package'], 2)

        self.assertEqual(by_name['Rice Demand'].customer_count, 4)
        self.assertEqual(by_name['Vegetable Only'].customer_count, 2)
        self.assertEqual(len(by_name['Vegetable Only'].package_contributions), 1)
        self.assertEqual(
            by_name['Vegetable Only'].package_contributions[0].package_name,
            'Premium Package',
        )
        self.assertEqual(by_name['Fish Only'].customer_count, 2)
        self.assertEqual(
            by_name['Fish Only'].package_contributions[0].package_name,
            'Regular Package',
        )
        # 0.1 kg × 4 for Dal
        self.assertEqual(by_name['Dal Shared'].quantity, Decimal('0.400000'))

    def test_build_kitchen_requirement_packages_and_filter(self):
        from orders.services.meal_demand import build_kitchen_requirement

        payload = build_kitchen_requirement(
            self.service_date,
            'dinner',
            settings_obj=self.settings_obj,
        )
        self.assertEqual(len(payload['packages']), 2)
        self.assertEqual(payload['final_cooking_count'], 4)
        rice = next(i for i in payload['ingredients'] if i['name'] == 'Rice Demand')
        self.assertEqual(rice['customer_count'], 4)
        self.assertEqual(len(rice['package_contributions']), 2)
        self.assertIn('quantity_available', rice)

        filtered = build_kitchen_requirement(
            self.service_date,
            'dinner',
            package_public_id=self.premium.public_id,
            settings_obj=self.settings_obj,
        )
        self.assertEqual(len(filtered['packages']), 1)
        self.assertEqual(filtered['packages'][0]['package_name'], 'Premium Package')
        self.assertEqual(filtered['final_cooking_count'], 2)
        rice_f = next(i for i in filtered['ingredients'] if i['name'] == 'Rice Demand')
        self.assertEqual(rice_f['customer_count'], 2)
        self.assertEqual(len(rice_f['package_contributions']), 1)

    def test_freeze_ingredients_omits_contributions(self):
        demand = get_demand(self.service_date, 'dinner', settings_obj=self.settings_obj)
        ingredients, _ = get_ingredient_requirements(demand)
        from orders.services.meal_demand import _freeze_ingredients

        frozen = _freeze_ingredients(ingredients)
        self.assertTrue(frozen)
        self.assertNotIn('customer_count', frozen[0])
        self.assertNotIn('package_contributions', frozen[0])
        self.assertIn('quantity_available', frozen[0])

    def test_missing_menu_marks_incomplete(self):
        MonthlyMenuSlot.objects.filter(service_date=self.service_date).delete()
        demand = get_demand(self.service_date, 'dinner', settings_obj=self.settings_obj)
        ingredients, incomplete = get_ingredient_requirements(demand)
        self.assertTrue(incomplete)
        self.assertEqual(ingredients, [])

    def test_upsert_snapshot_idempotent_and_frozen(self):
        now = datetime(2026, 8, 5, 15, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        first = upsert_demand_snapshots_for_slot(
            self.service_date, 'dinner', now=now, settings_obj=self.settings_obj
        )
        self.assertEqual(len(first), 2)
        rice_qty = first[0].ingredient_requirements
        self.rice.customers_per_kg = Decimal('10.00')
        self.rice.save(update_fields=['customers_per_kg'])
        second = upsert_demand_snapshots_for_slot(
            self.service_date, 'dinner', now=now, settings_obj=self.settings_obj
        )
        self.assertEqual(MealDemandSnapshot.objects.count(), 2)
        # Live recompute would change rice qty, but we re-freeze from live on upsert;
        # history API still returns DB rows. Verify row count stable:
        self.assertEqual(len(second), 2)
        # After yield change, upsert refreshes frozen payload from live math:
        refreshed = MealDemandSnapshot.objects.get(package=self.premium)
        self.assertNotEqual(refreshed.ingredient_requirements, rice_qty)


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MealDemandAPITestCase(APITestCase):
    def setUp(self):
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.admin_user = User.objects.create_user(
            username='demand_admin',
            email='demand_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(self.admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='demand_customer',
            email='demand_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1711999888',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.meal = MealCategory.objects.create(
            meal_name='Demand Meal',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('api-demand.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.service_date = date(2026, 8, 5)
        order = Order.objects.create(
            customer=self.customer_profile,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_type_snapshot=self.meal.meal_type,
            meal_period_snapshot=self.meal.meal_period,
            total_price_snapshot=self.meal.total_price,
            per_meal_price_snapshot=Decimal('100.00'),
            order_status=Order.OrderStatus.ACTIVE,
            order_start_date=self.service_date,
            order_end_date=self.service_date,
            service_days_count=1,
            order_month='2026-08',
        )
        OrderDelivery.objects.create(
            order=order,
            service_date=self.service_date,
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        OrderDelivery.objects.create(
            order=order,
            service_date=self.service_date,
            meal_period=OrderDelivery.MealPeriod.DINNER,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.CUSTOMER,
        )
        MealOffSettings.load()

        self.stats_url = reverse('orders:meal-statistics')
        self.kitchen_url = reverse('orders:kitchen-today-meal-requirement')
        self.history_url = reverse('orders:meal-history')

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_statistics_admin_success_both_periods(self):
        self._auth(self.admin_token)
        response = self.client.get(self.stats_url, {'service_date': '2026-08-05'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['periods']), 2)
        by_period = {p['meal_period']: p for p in response.data['periods']}
        self.assertEqual(by_period['lunch']['expected_meal_count'], 1)
        self.assertEqual(by_period['lunch']['final_cooking_count'], 1)
        self.assertEqual(by_period['dinner']['meal_off_count'], 1)
        self.assertEqual(by_period['dinner']['final_cooking_count'], 0)

    def test_statistics_period_filter(self):
        self._auth(self.admin_token)
        response = self.client.get(
            self.stats_url,
            {'service_date': '2026-08-05', 'meal_period': 'dinner'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['periods']), 1)
        self.assertEqual(response.data['periods'][0]['meal_period'], 'dinner')

    def test_statistics_customer_denied(self):
        self._auth(self.customer_token)
        response = self.client.get(self.stats_url, {'service_date': '2026-08-05'})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    @patch('orders.services.meal_demand.meal_off_business_now')
    def test_kitchen_default_morning_lunch(self, mock_now):
        mock_now.return_value = datetime(2026, 8, 5, 10, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        self._auth(self.admin_token)
        response = self.client.get(self.kitchen_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['service_date'], '2026-08-05')
        self.assertEqual(response.data['meal_period'], 'lunch')
        self.assertEqual(response.data['final_cooking_count'], 1)
        self.assertIn('ingredients', response.data)
        self.assertIn('packages', response.data)

    @patch('orders.services.meal_demand.meal_off_business_now')
    def test_kitchen_default_afternoon_dinner(self, mock_now):
        mock_now.return_value = datetime(2026, 8, 5, 15, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        self._auth(self.admin_token)
        response = self.client.get(self.kitchen_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['meal_period'], 'dinner')
        self.assertEqual(response.data['final_cooking_count'], 0)

    def test_kitchen_explicit_override(self):
        self._auth(self.admin_token)
        response = self.client.get(
            self.kitchen_url,
            {'service_date': '2026-08-05', 'meal_period': 'lunch'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['meal_period'], 'lunch')
        self.assertIn('packages', response.data)
        self.assertEqual(len(response.data['packages']), 1)
        self.assertEqual(response.data['packages'][0]['final_cooking_count'], 1)

    def test_kitchen_package_filter(self):
        self._auth(self.admin_token)
        response = self.client.get(
            self.kitchen_url,
            {
                'service_date': '2026-08-05',
                'meal_period': 'lunch',
                'package_public_id': str(self.meal.public_id),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['packages']), 1)
        self.assertEqual(
            str(response.data['packages'][0]['package_public_id']),
            str(self.meal.public_id),
        )

    def test_kitchen_package_filter_not_found(self):
        self._auth(self.admin_token)
        response = self.client.get(
            self.kitchen_url,
            {
                'service_date': '2026-08-05',
                'meal_period': 'lunch',
                'package_public_id': '00000000-0000-0000-0000-000000000099',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_kitchen_invalid_meal_period(self):
        self._auth(self.admin_token)
        response = self.client.get(
            self.kitchen_url,
            {'service_date': '2026-08-05', 'meal_period': 'brunch'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kitchen_invalid_service_date(self):
        self._auth(self.admin_token)
        response = self.client.get(
            self.kitchen_url,
            {'service_date': '08-05-2026', 'meal_period': 'lunch'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kitchen_customer_denied(self):
        self._auth(self.customer_token)
        response = self.client.get(self.kitchen_url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_history_after_confirm_and_frozen_qty(self):
        self._auth(self.admin_token)
        rice = Ingredient.objects.create(
            name='Hist Rice',
            price_per_kg=Decimal('70.00'),
            customers_per_kg=Decimal('2.00'),
            is_active=True,
        )
        cycle = MealCycle.objects.create(year=2026, month=8)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=self.meal,
            status=MealCyclePlan.Status.FINALIZED,
        )
        schedule = MonthlyMenuSchedule.objects.create(
            plan=plan,
            status=MonthlyMenuSchedule.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        slot = MonthlyMenuSlot.objects.create(
            schedule=schedule,
            service_date=self.service_date,
            meal_period=MonthlyMenuSlot.MealPeriod.LUNCH,
        )
        MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=rice)

        now = datetime(2026, 8, 5, 12, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        # Lunch deadline is previous day 23:59 → confirmed on Aug 5
        upsert_demand_snapshots_for_slot(
            self.service_date, 'lunch', now=now, settings_obj=MealOffSettings.load()
        )
        snap = MealDemandSnapshot.objects.get(package=self.meal, meal_period='lunch')
        frozen_qty = snap.ingredient_requirements[0]['quantity']

        rice.customers_per_kg = Decimal('10.00')
        rice.save(update_fields=['customers_per_kg'])

        response = self.client.get(self.history_url, {'service_date': '2026-08-05'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['ingredient_requirements'][0]['quantity'], frozen_qty)

        call_command(
            'confirm_meal_demand_snapshots',
            '--now',
            '2026-08-05T16:00:00',
            '--lookback-days',
            '3',
        )
        self.assertGreaterEqual(MealDemandSnapshot.objects.count(), 1)

    def test_history_customer_denied(self):
        self._auth(self.customer_token)
        response = self.client.get(self.history_url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
