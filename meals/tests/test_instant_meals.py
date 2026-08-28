"""Tests for Instant Meal settings and public list API."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import (
    Ingredient,
    InstantMealSettings,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MealCyclePlanLine,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from meals.services.instant_meals import (
    compute_instant_slot_price,
    list_instant_meals,
    update_instant_meal_settings,
)
from meals.tests.helpers import ensure_operational_cost_month
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class InstantMealSettingsAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='instant-admin',
            email='instant-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='instant-customer',
            email='instant-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345701',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.url = reverse('meals:instant-meal-settings')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def test_defaults_on_get(self):
        self._auth_admin()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['profit_percent']), Decimal('50.00'))
        self.assertEqual(response.data['duration_days'], 7)

    def test_admin_patches_profit_and_duration(self):
        self._auth_admin()
        response = self.client.patch(
            self.url,
            {'profit_percent': '70.00', 'duration_days': 15},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['profit_percent']), Decimal('70.00'))
        self.assertEqual(response.data['duration_days'], 15)
        settings_obj = InstantMealSettings.load()
        self.assertEqual(settings_obj.profit_percent, Decimal('70.00'))
        self.assertEqual(settings_obj.duration_days, 15)

    def test_invalid_duration_rejected(self):
        self._auth_admin()
        before = InstantMealSettings.load()
        response = self.client.patch(self.url, {'duration_days': 10}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration_days', response.data)
        before.refresh_from_db()
        self.assertEqual(before.duration_days, 7)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_unauthenticated_denied(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


@override_settings(MEDIA_ROOT='test_media')
class InstantMealListAPITests(APITestCase):
    def setUp(self):
        self.today = date(2026, 8, 28)
        ensure_operational_cost_month(
            2026,
            8,
            target_meal_quantity=100,
            items=[('Rent', Decimal('1000.00'))],
        )
        # per_meal_op = 10.00

        self.student = MealCategory.objects.create(
            meal_name='Student Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('student.jpg'),
        )
        self.regular = MealCategory.objects.create(
            meal_name='Regular Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('regular.jpg'),
        )
        self.chicken = Ingredient.objects.create(
            name='Chicken',
            cost_per_customer=Decimal('20.00'),
        )
        self.rice = Ingredient.objects.create(
            name='Rice',
            cost_per_customer=Decimal('12.00'),
        )
        self.dal = Ingredient.objects.create(
            name='Dal',
            cost_per_customer=Decimal('8.00'),
        )
        self.fish = Ingredient.objects.create(
            name='Fish',
            cost_per_customer=Decimal('25.00'),
        )

        self.cycle = MealCycle.objects.create(year=2026, month=8)
        self.student_plan = self._make_plan(self.student, profit=Decimal('10.00'))
        self.regular_plan = self._make_plan(self.regular, profit=Decimal('10.00'))

        InstantMealSettings.load()
        update_instant_meal_settings(duration_days=7, profit_percent=Decimal('50.00'))

        self.list_url = reverse('meals:instant-meals')

    def _make_plan(self, meal, *, profit):
        plan = MealCyclePlan.objects.create(
            cycle=self.cycle,
            meal_category=meal,
            profit_percent=profit,
            status=MealCyclePlan.Status.FINALIZED,
        )
        total = self.cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total // 2,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.fish,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total - (total // 2),
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.rice,
            product_role=MealCyclePlanLine.ProductRole.STAPLE,
            servings_count=total,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.dal,
            product_role=MealCyclePlanLine.ProductRole.SIDE,
            servings_count=total,
        )
        return plan

    def _publish_slot(
        self,
        plan,
        *,
        service_date,
        meal_period,
        ingredients,
        ingredient_cost,
        subscriber_price,
        status=MonthlyMenuSchedule.Status.PUBLISHED,
    ):
        schedule, _ = MonthlyMenuSchedule.objects.get_or_create(
            plan=plan,
            defaults={
                'status': status,
                'published_at': timezone.now() if status == MonthlyMenuSchedule.Status.PUBLISHED else None,
            },
        )
        if schedule.status != status:
            schedule.status = status
            schedule.published_at = (
                timezone.now() if status == MonthlyMenuSchedule.Status.PUBLISHED else None
            )
            schedule.save(update_fields=['status', 'published_at', 'updated_at'])

        slot = MonthlyMenuSlot.objects.create(
            schedule=schedule,
            service_date=service_date,
            meal_period=meal_period,
            ingredient_cost_snapshot=ingredient_cost,
            operational_cost_snapshot=Decimal('10.00'),
            profit_snapshot=Decimal('4.00'),
            final_meal_price_snapshot=subscriber_price,
        )
        for ingredient in ingredients:
            MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=ingredient)
        return slot

    def test_list_published_only_excludes_past_and_draft(self):
        self._publish_slot(
            self.student_plan,
            service_date=self.today,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice, self.dal],
            ingredient_cost=Decimal('40.00'),
            subscriber_price=Decimal('54.00'),
        )
        self._publish_slot(
            self.student_plan,
            service_date=self.today - timedelta(days=1),
            meal_period='lunch',
            ingredients=[self.chicken, self.rice],
            ingredient_cost=Decimal('32.00'),
            subscriber_price=Decimal('45.20'),
        )
        draft_plan_meal = MealCategory.objects.create(
            meal_name='Draft Package',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            meal_thumbnail=make_test_image('draft.jpg'),
        )
        draft_plan = self._make_plan(draft_plan_meal, profit=Decimal('10.00'))
        self._publish_slot(
            draft_plan,
            service_date=self.today,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice],
            ingredient_cost=Decimal('32.00'),
            subscriber_price=Decimal('45.20'),
            status=MonthlyMenuSchedule.Status.DRAFT,
        )

        with patch('meals.services.instant_meals.timezone.localdate', return_value=self.today):
            response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['service_date'], '2026-08-28')
        self.assertEqual(results[0]['package_name'], 'Student Package')
        self.assertNotIn('subscription_message', results[0])

    def test_duration_window_and_ordering_and_multi_package(self):
        update_instant_meal_settings(duration_days=3)
        day0 = self.today
        day1 = self.today + timedelta(days=1)
        day2 = self.today + timedelta(days=2)
        day3 = self.today + timedelta(days=3)

        self._publish_slot(
            self.student_plan,
            service_date=day1,
            meal_period='dinner',
            ingredients=[self.fish, self.rice],
            ingredient_cost=Decimal('37.00'),
            subscriber_price=Decimal('50.70'),
        )
        self._publish_slot(
            self.student_plan,
            service_date=day1,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice, self.dal],
            ingredient_cost=Decimal('40.00'),
            subscriber_price=Decimal('54.00'),
        )
        self._publish_slot(
            self.regular_plan,
            service_date=day1,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice, self.dal],
            ingredient_cost=Decimal('40.00'),
            subscriber_price=Decimal('54.00'),
        )
        self._publish_slot(
            self.student_plan,
            service_date=day0,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice],
            ingredient_cost=Decimal('32.00'),
            subscriber_price=Decimal('45.20'),
        )
        self._publish_slot(
            self.student_plan,
            service_date=day2,
            meal_period='lunch',
            ingredients=[self.chicken, self.dal],
            ingredient_cost=Decimal('28.00'),
            subscriber_price=Decimal('40.80'),
        )
        self._publish_slot(
            self.student_plan,
            service_date=day3,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice],
            ingredient_cost=Decimal('32.00'),
            subscriber_price=Decimal('45.20'),
        )

        with patch('meals.services.instant_meals.timezone.localdate', return_value=self.today):
            response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        # day0 lunch student, day1 lunch regular, day1 lunch student, day1 dinner student, day2 lunch student
        # day3 excluded (outside 3-day window)
        self.assertEqual(len(results), 5)
        dates = [r['service_date'] for r in results]
        self.assertEqual(dates, [
            '2026-08-28',
            '2026-08-29',
            '2026-08-29',
            '2026-08-29',
            '2026-08-30',
        ])
        day1_cards = [r for r in results if r['service_date'] == '2026-08-29']
        self.assertEqual(day1_cards[0]['meal_period'], 'lunch')
        self.assertEqual(day1_cards[0]['package_name'], 'Regular Package')
        self.assertEqual(day1_cards[1]['meal_period'], 'lunch')
        self.assertEqual(day1_cards[1]['package_name'], 'Student Package')
        self.assertEqual(day1_cards[2]['meal_period'], 'dinner')

    def test_instant_price_formula_and_isolation(self):
        slot = self._publish_slot(
            self.student_plan,
            service_date=self.today,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice, self.dal],
            ingredient_cost=Decimal('40.00'),
            subscriber_price=Decimal('54.00'),
        )
        locked_subscriber = slot.final_meal_price_snapshot
        plan_profit = self.student_plan.profit_percent

        # 40 + 10 + 50% of 40 = 70
        with patch('meals.services.instant_meals.timezone.localdate', return_value=self.today):
            cards = list_instant_meals()
        self.assertEqual(len(cards), 1)
        self.assertEqual(Decimal(cards[0]['price']), Decimal('70.00'))
        self.assertEqual(Decimal(cards[0]['ingredient_cost']), Decimal('40.00'))
        self.assertEqual(Decimal(cards[0]['operational_cost']), Decimal('10.00'))
        self.assertEqual(Decimal(cards[0]['subscriber_price']), Decimal('54.00'))

        update_instant_meal_settings(profit_percent=Decimal('70.00'))
        priced = compute_instant_slot_price(slot, profit_percent=Decimal('70.00'))
        # 40 + 10 + 28 = 78
        self.assertEqual(priced['price'], Decimal('78.00'))

        slot.refresh_from_db()
        self.student_plan.refresh_from_db()
        self.assertEqual(slot.final_meal_price_snapshot, locked_subscriber)
        self.assertEqual(self.student_plan.profit_percent, plan_profit)

        with patch('meals.services.instant_meals.timezone.localdate', return_value=self.today):
            response = self.client.get(self.list_url)
        self.assertEqual(Decimal(response.data['results'][0]['price']), Decimal('78.00'))

    def test_skips_unpriceable_slot_without_failing_list(self):
        # September has no operational cost month configured
        sept_cycle = MealCycle.objects.create(year=2026, month=9)
        sept_plan = MealCyclePlan.objects.create(
            cycle=sept_cycle,
            meal_category=self.student,
            profit_percent=Decimal('10.00'),
            status=MealCyclePlan.Status.FINALIZED,
        )
        MealCyclePlanLine.objects.create(
            plan=sept_plan,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=60,
        )
        good = self._publish_slot(
            self.student_plan,
            service_date=self.today,
            meal_period='lunch',
            ingredients=[self.chicken, self.rice],
            ingredient_cost=Decimal('32.00'),
            subscriber_price=Decimal('45.20'),
        )
        schedule, _ = MonthlyMenuSchedule.objects.get_or_create(plan=sept_plan)
        schedule.status = MonthlyMenuSchedule.Status.PUBLISHED
        schedule.published_at = timezone.now()
        schedule.save()
        bad = MonthlyMenuSlot.objects.create(
            schedule=schedule,
            service_date=self.today + timedelta(days=4),
            meal_period='lunch',
            ingredient_cost_snapshot=None,
            operational_cost_snapshot=None,
            final_meal_price_snapshot=None,
        )
        MonthlyMenuSlotItem.objects.create(slot=bad, ingredient=self.chicken)

        update_instant_meal_settings(duration_days=7)
        with patch('meals.services.instant_meals.timezone.localdate', return_value=self.today):
            cards = list_instant_meals()
        public_ids = {c['public_id'] for c in cards}
        self.assertIn(
            f'{self.student.public_id}:{good.service_date.isoformat()}:lunch',
            public_ids,
        )
        self.assertNotIn(
            f'{self.student.public_id}:{bad.service_date.isoformat()}:lunch',
            public_ids,
        )
