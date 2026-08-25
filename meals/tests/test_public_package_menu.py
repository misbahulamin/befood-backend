from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
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
from meals.services.menu_schedule import expected_slot_keys, publish_schedule, replace_schedule_assignments
from user_management.models import AdminProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class PublicPackageMenuAPITestCase(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='public-menu-admin',
            email='public-menu-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)

        self.meal = MealCategory.objects.create(
            meal_name='Premium Package',
            total_price=Decimal('5000.00'),
            meal_type='monthly',
            meal_period='both',
            meal_thumbnail=make_test_image('premium.jpg'),
        )
        self.chicken = Ingredient.objects.create(
            name='Chicken',
            price_per_kg=Decimal('130.00'),
            customers_per_kg=Decimal('10.00'),
        )
        self.beef = Ingredient.objects.create(
            name='Beef',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
        )
        self.rice = Ingredient.objects.create(
            name='Rice',
            price_per_kg=Decimal('70.00'),
            customers_per_kg=Decimal('7.00'),
        )
        self.url = reverse('meals:public-package-menu')

    def _finalize_plan(self, year, month, chicken_count, beef_count):
        from meals.tests.helpers import ensure_operational_cost_month

        ensure_operational_cost_month(year, month, items=[])
        cycle, _ = MealCycle.objects.get_or_create(year=year, month=month)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=self.meal)
        total = cycle.total_meals
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=chicken_count,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=beef_count,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.rice,
            product_role=MealCyclePlanLine.ProductRole.STAPLE,
            servings_count=total,
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

    def test_public_published_menu_without_auth(self):
        schedule = self._create_published_schedule(2026, 7)
        expected_days = schedule.slots.count()

        response = self.client.get(
            self.url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 7},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['schedule_published'])
        self.assertEqual(response.data['meal_public_id'], str(self.meal.public_id))
        self.assertEqual(response.data['meal_name'], 'Premium Package')
        self.assertEqual(len(response.data['days']), expected_days)
        meta = response.data['meta']
        self.assertEqual(meta['cycle_days'], 31)
        self.assertEqual(meta['total_meals'], 62)
        self.assertEqual(meta['meal_period'], 'both')
        self.assertEqual(meta['meal_period_display'], 'Both')

    def test_public_unpublished_returns_empty_days(self):
        self._create_draft_schedule(2026, 7)

        response = self.client.get(
            self.url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 7},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['schedule_published'])
        self.assertEqual(response.data['days'], [])
        self.assertEqual(response.data['meta']['cycle_days'], 31)
        self.assertEqual(response.data['meta']['meal_period'], 'both')

    def test_missing_meal_public_id_returns_400(self):
        response = self.client.get(self.url, {'year': 2026, 'month': 7})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_meal_returns_404(self):
        response = self.client.get(
            self.url,
            {
                'meal_public_id': '00000000-0000-0000-0000-000000000099',
                'year': 2026,
                'month': 7,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_inactive_meal_returns_404(self):
        self.meal.is_active = False
        self.meal.save(update_fields=['is_active'])

        response = self.client.get(
            self.url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 7},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_month_query_returns_400(self):
        response = self.client.get(
            self.url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_january_cycle_days_meta(self):
        self._create_published_schedule(2026, 1)

        response = self.client.get(
            self.url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['meta']['cycle_days'], 31)

    def test_lunch_only_package_meta(self):
        self.meal.meal_period = MealCategory.MealPeriod.LUNCH
        self.meal.save(update_fields=['meal_period'])
        MealCycle.objects.get_or_create(year=2026, month=4)

        response = self.client.get(
            self.url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 4},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['schedule_published'])
        self.assertEqual(response.data['meta']['meal_period'], 'lunch')
        self.assertEqual(response.data['meta']['meal_period_display'], 'Lunch')
        self.assertEqual(response.data['meta']['cycle_days'], 30)
        self.assertEqual(response.data['meta']['total_meals'], 30)
