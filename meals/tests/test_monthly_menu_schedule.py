from datetime import date, datetime, time
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
from meals.services.cycle_calculations import finalize_plan, reopen_plan
from meals.services.menu_schedule import (
    expected_slot_keys,
    publish_schedule,
    replace_schedule_assignments,
)
from meals.services.menu_sync import build_sync_suggestion
from orders.models import Order
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class MonthlyMenuScheduleAPITestCase(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='menu-admin',
            email='menu-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='menu-customer',
            email='menu-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345699',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.regular = MealCategory.objects.create(
            meal_name='Regular Package',
            total_price=Decimal('3000.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('regular.jpg'),
        )
        self.student = MealCategory.objects.create(
            meal_name='Student Package',
            total_price=Decimal('2500.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('student.jpg'),
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

        self.schedules_url = reverse('meals:menu-schedules-list')
        self.reveal_url = reverse('meals:menu-reveal-settings')
        self.today_url = reverse('meals:today-menu')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _finalize_plan(self, meal, year, month, chicken_count, beef_count, rice_count=None):
        cycle, _ = MealCycle.objects.get_or_create(year=year, month=month)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=meal)
        total = cycle.total_meals
        if rice_count is None:
            rice_count = total
        MealCyclePlanLine.objects.create(
            plan=plan, ingredient=self.chicken, servings_count=chicken_count
        )
        MealCyclePlanLine.objects.create(
            plan=plan, ingredient=self.beef, servings_count=beef_count
        )
        MealCyclePlanLine.objects.create(
            plan=plan, ingredient=self.rice, servings_count=rice_count
        )
        assert chicken_count + beef_count == total
        return finalize_plan(plan)

    def _full_main_assignments(self, plan, chicken_slots, beef_slots):
        """Build assignments covering every slot with exactly one main (+ rice)."""
        keys = expected_slot_keys(plan.cycle.year, plan.cycle.month)
        assert len(chicken_slots) + len(beef_slots) == len(keys)
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

    def _split_keys(self, plan, chicken_count):
        keys = expected_slot_keys(plan.cycle.year, plan.cycle.month)
        return keys[:chicken_count], keys[chicken_count:]

    # --- 6.1 create / quota / publish ---

    def test_create_requires_finalized_plan(self):
        cycle = MealCycle.objects.create(year=2026, month=4)
        draft = MealCyclePlan.objects.create(cycle=cycle, meal_category=self.regular)
        self._auth_admin()
        response = self.client.post(
            self.schedules_url,
            {'plan_id': draft.pk, 'notes': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_cannot_list_schedules(self):
        self._auth_customer()
        response = self.client.get(self.schedules_url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_anonymous_cannot_list_schedules(self):
        self.client.credentials()
        response = self.client.get(self.schedules_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_quota_overflow_and_duplicate_main_rejected(self):
        plan = self._finalize_plan(self.regular, 2026, 4, chicken_count=10, beef_count=50)
        self._auth_admin()
        create = self.client.post(self.schedules_url, {'plan_id': plan.pk}, format='json')
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        schedule_id = create.data['id']

        # 11 chicken slots > quota 10
        keys = expected_slot_keys(2026, 4)
        overflow = [
            {
                'service_date': k[0].isoformat(),
                'meal_period': k[1],
                'ingredient_ids': [self.chicken.id],
            }
            for k in keys[:11]
        ]
        resp = self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': schedule_id}),
            {'assignments': overflow},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # Duplicate mains on one slot
        dup = [
            {
                'service_date': '2026-04-01',
                'meal_period': 'lunch',
                'ingredient_ids': [self.chicken.id, self.beef.id],
            }
        ]
        resp2 = self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': schedule_id}),
            {'assignments': dup},
            format='json',
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_requires_full_main_coverage(self):
        plan = self._finalize_plan(self.regular, 2026, 4, chicken_count=10, beef_count=50)
        self._auth_admin()
        create = self.client.post(self.schedules_url, {'plan_id': plan.pk}, format='json')
        schedule_id = create.data['id']
        # Only one slot filled
        self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': schedule_id}),
            {
                'assignments': [
                    {
                        'service_date': '2026-04-01',
                        'meal_period': 'lunch',
                        'ingredient_ids': [self.chicken.id],
                    }
                ]
            },
            format='json',
        )
        pub = self.client.post(
            reverse('meals:menu-schedules-publish', kwargs={'pk': schedule_id})
        )
        self.assertEqual(pub.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('incomplete_slots', pub.data)

    def test_publish_full_month_succeeds(self):
        plan = self._finalize_plan(self.regular, 2026, 4, chicken_count=10, beef_count=50)
        chicken_keys, beef_keys = self._split_keys(plan, 10)
        assignments = self._full_main_assignments(plan, chicken_keys, beef_keys)
        self._auth_admin()
        create = self.client.post(self.schedules_url, {'plan_id': plan.pk}, format='json')
        schedule_id = create.data['id']
        put = self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': schedule_id}),
            {'assignments': assignments},
            format='json',
        )
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        pub = self.client.post(
            reverse('meals:menu-schedules-publish', kwargs={'pk': schedule_id})
        )
        self.assertEqual(pub.status_code, status.HTTP_200_OK)
        self.assertEqual(pub.data['status'], 'published')

    # --- 6.2 reopen guards ---

    def test_reopen_blocked_when_schedule_published(self):
        plan = self._finalize_plan(self.regular, 2026, 4, chicken_count=10, beef_count=50)
        chicken_keys, beef_keys = self._split_keys(plan, 10)
        assignments = self._full_main_assignments(plan, chicken_keys, beef_keys)
        self._auth_admin()
        create = self.client.post(self.schedules_url, {'plan_id': plan.pk}, format='json')
        schedule_id = create.data['id']
        self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': schedule_id}),
            {'assignments': assignments},
            format='json',
        )
        self.client.post(reverse('meals:menu-schedules-publish', kwargs={'pk': schedule_id}))
        reopen = self.client.post(reverse('meals:cycle-plans-reopen', kwargs={'pk': plan.pk}))
        self.assertEqual(reopen.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reopen_deletes_draft_schedule(self):
        plan = self._finalize_plan(self.regular, 2026, 4, chicken_count=10, beef_count=50)
        self._auth_admin()
        create = self.client.post(self.schedules_url, {'plan_id': plan.pk}, format='json')
        schedule_id = create.data['id']
        self.assertTrue(MonthlyMenuSchedule.objects.filter(pk=schedule_id).exists())
        reopen = self.client.post(reverse('meals:cycle-plans-reopen', kwargs={'pk': plan.pk}))
        self.assertEqual(reopen.status_code, status.HTTP_200_OK)
        self.assertFalse(MonthlyMenuSchedule.objects.filter(pk=schedule_id).exists())

    # --- 6.3 sync ---

    def test_sync_suggestion_respects_unequal_chicken_quota(self):
        # April: 60 meals. Regular chicken 12, Student chicken 10.
        regular_plan = self._finalize_plan(
            self.regular, 2026, 4, chicken_count=12, beef_count=48
        )
        student_plan = self._finalize_plan(
            self.student, 2026, 4, chicken_count=10, beef_count=50
        )
        chicken_keys, beef_keys = self._split_keys(regular_plan, 12)
        regular_assignments = self._full_main_assignments(
            regular_plan, chicken_keys, beef_keys
        )

        self._auth_admin()
        r_create = self.client.post(
            self.schedules_url, {'plan_id': regular_plan.pk}, format='json'
        )
        s_create = self.client.post(
            self.schedules_url, {'plan_id': student_plan.pk}, format='json'
        )
        regular_id = r_create.data['id']
        student_id = s_create.data['id']
        self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': regular_id}),
            {'assignments': regular_assignments},
            format='json',
        )

        suggestion = self.client.post(
            reverse('meals:menu-schedules-sync-suggestions', kwargs={'pk': student_id}),
            {'source_schedule_id': regular_id},
            format='json',
        )
        self.assertEqual(suggestion.status_code, status.HTTP_200_OK)
        chicken_assigned = 0
        for entry in suggestion.data['assignments']:
            if self.chicken.id in entry['ingredient_ids']:
                chicken_assigned += 1
        self.assertEqual(chicken_assigned, 10)
        self.assertTrue(
            any(row['ingredient_id'] == self.chicken.id and row['remaining'] == 0
                for row in suggestion.data['remaining_quota'])
            or chicken_assigned == 10
        )

        apply = self.client.post(
            reverse('meals:menu-schedules-apply-sync', kwargs={'pk': student_id}),
            {'source_schedule_id': regular_id},
            format='json',
        )
        self.assertEqual(apply.status_code, status.HTTP_200_OK)
        used_chicken = next(
            row for row in apply.data['quota_summary'] if row['ingredient_id'] == self.chicken.id
        )
        self.assertEqual(used_chicken['used'], 10)
        self.assertLessEqual(used_chicken['used'], used_chicken['planned'])

    def test_divergence_warning_when_mains_differ(self):
        regular_plan = self._finalize_plan(
            self.regular, 2026, 4, chicken_count=30, beef_count=30
        )
        student_plan = self._finalize_plan(
            self.student, 2026, 4, chicken_count=30, beef_count=30
        )
        keys = expected_slot_keys(2026, 4)
        # Regular: chicken first half, beef second; Student opposite
        r_chicken, r_beef = keys[:30], keys[30:]
        s_chicken, s_beef = keys[30:], keys[:30]
        self._auth_admin()
        r_id = self.client.post(
            self.schedules_url, {'plan_id': regular_plan.pk}, format='json'
        ).data['id']
        s_id = self.client.post(
            self.schedules_url, {'plan_id': student_plan.pk}, format='json'
        ).data['id']
        self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': r_id}),
            {'assignments': self._full_main_assignments(regular_plan, r_chicken, r_beef)},
            format='json',
        )
        self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': s_id}),
            {'assignments': self._full_main_assignments(student_plan, s_chicken, s_beef)},
            format='json',
        )
        suggestion = self.client.post(
            reverse('meals:menu-schedules-sync-suggestions', kwargs={'pk': s_id}),
            {'source_schedule_id': r_id},
            format='json',
        )
        self.assertEqual(suggestion.status_code, status.HTTP_200_OK)
        self.assertTrue(len(suggestion.data['divergence_warnings']) > 0)

    # --- 6.4 reveal + today menu ---

    def test_reveal_settings_admin_only(self):
        self._auth_customer()
        response = self.client.get(self.reveal_url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        self._auth_admin()
        get_resp = self.client.get(self.reveal_url)
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data['lunch_reveal_time'], '08:00:00')
        patch = self.client.patch(
            self.reveal_url,
            {'lunch_reveal_time': '07:30:00', 'dinner_reveal_time': '15:30:00'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['lunch_reveal_time'], '07:30:00')

    def test_today_menu_auth_and_order_scope_with_reveal(self):
        plan = self._finalize_plan(self.regular, 2026, 7, chicken_count=20, beef_count=42)
        chicken_keys, beef_keys = self._split_keys(plan, 20)
        assignments = self._full_main_assignments(plan, chicken_keys, beef_keys)
        self._auth_admin()
        schedule_id = self.client.post(
            self.schedules_url, {'plan_id': plan.pk}, format='json'
        ).data['id']
        self.client.put(
            reverse('meals:menu-schedules-assignments', kwargs={'pk': schedule_id}),
            {'assignments': assignments},
            format='json',
        )
        self.client.post(reverse('meals:menu-schedules-publish', kwargs={'pk': schedule_id}))

        Order.objects.create(
            customer=self.customer_profile,
            meal=self.regular,
            meal_name_snapshot=self.regular.meal_name,
            meal_type_snapshot=self.regular.meal_type,
            total_price_snapshot=self.regular.total_price,
            per_meal_price_snapshot=Decimal('50.00'),
            order_status=Order.OrderStatus.CONFIRMED,
            order_start_date=date(2026, 7, 1),
            order_end_date=date(2026, 7, 31),
            service_days_count=31,
            order_month='2026-07',
        )

        tz = ZoneInfo('Asia/Dhaka')

        # Unauthenticated
        self.client.credentials()
        self.assertEqual(
            self.client.get(self.today_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self._auth_customer()

        from meals.services.today_menu import build_today_menu_for_customer

        before_lunch = datetime(2026, 7, 22, 7, 0, tzinfo=tz)
        payload = build_today_menu_for_customer(
            self.customer_profile, now=before_lunch
        )
        self.assertEqual(payload['visible_periods'], [])
        self.assertEqual(len(payload['packages']), 1)
        self.assertEqual(payload['packages'][0]['periods'], [])

        after_lunch = datetime(2026, 7, 22, 12, 0, tzinfo=tz)
        payload_lunch = build_today_menu_for_customer(
            self.customer_profile, now=after_lunch
        )
        self.assertEqual(payload_lunch['visible_periods'], ['lunch'])
        self.assertEqual(len(payload_lunch['packages'][0]['periods']), 1)
        self.assertEqual(payload_lunch['packages'][0]['periods'][0]['meal_period'], 'lunch')
        self.assertTrue(len(payload_lunch['packages'][0]['periods'][0]['ingredients']) >= 1)

        after_dinner = datetime(2026, 7, 22, 17, 0, tzinfo=tz)
        payload_dinner = build_today_menu_for_customer(
            self.customer_profile, now=after_dinner
        )
        self.assertEqual(payload_dinner['visible_periods'], ['lunch', 'dinner'])
        self.assertEqual(len(payload_dinner['packages'][0]['periods']), 2)

        # No order for student package — only regular appears
        meal_ids = [p['meal_category_id'] for p in payload_dinner['packages']]
        self.assertEqual(meal_ids, [self.regular.id])


class MenuSyncServiceTestCase(APITestCase):
    def setUp(self):
        self.regular = MealCategory.objects.create(
            meal_name='Regular',
            total_price=Decimal('1000.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('r.jpg'),
        )
        self.student = MealCategory.objects.create(
            meal_name='Student',
            total_price=Decimal('800.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('s.jpg'),
        )
        self.chicken = Ingredient.objects.create(
            name='ChickenSync',
            cost_per_customer=Decimal('10.00'),
            product_role=Ingredient.ProductRole.MAIN,
        )
        self.beef = Ingredient.objects.create(
            name='BeefSync',
            cost_per_customer=Decimal('12.00'),
            product_role=Ingredient.ProductRole.MAIN,
        )

    def test_service_unequal_quota_mirror(self):
        cycle = MealCycle.objects.create(year=2026, month=4)
        r_plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=self.regular,
            status=MealCyclePlan.Status.FINALIZED,
        )
        s_plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=self.student,
            status=MealCyclePlan.Status.FINALIZED,
        )
        MealCyclePlanLine.objects.create(plan=r_plan, ingredient=self.chicken, servings_count=12)
        MealCyclePlanLine.objects.create(plan=r_plan, ingredient=self.beef, servings_count=48)
        MealCyclePlanLine.objects.create(plan=s_plan, ingredient=self.chicken, servings_count=10)
        MealCyclePlanLine.objects.create(plan=s_plan, ingredient=self.beef, servings_count=50)

        r_sched = MonthlyMenuSchedule.objects.create(plan=r_plan)
        s_sched = MonthlyMenuSchedule.objects.create(plan=s_plan)
        keys = expected_slot_keys(2026, 4)
        assignments = []
        for i, key in enumerate(keys):
            main = self.chicken.id if i < 12 else self.beef.id
            assignments.append(
                {
                    'service_date': key[0],
                    'meal_period': key[1],
                    'ingredient_ids': [main],
                }
            )
        replace_schedule_assignments(r_sched, assignments)
        suggestion = build_sync_suggestion(r_sched, s_sched)
        chicken_count = sum(
            1 for a in suggestion['assignments'] if self.chicken.id in a['ingredient_ids']
        )
        self.assertEqual(chicken_count, 10)
