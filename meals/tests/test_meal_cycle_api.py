from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import Ingredient, MealCategory, MealCycle, MealCyclePlan, MealCyclePlanLine
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class MealCycleAPITestCase(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='verified-admin',
            email='verified-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='customer-user',
            email='customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345678',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.meal = MealCategory.objects.create(
            meal_name='Monthly Chicken Plan',
            total_price=Decimal('3000.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('monthly.jpg'),
        )
        self.chicken = Ingredient.objects.create(
            name='Chicken',
            price_per_kg=Decimal('130.00'),
            customers_per_kg=Decimal('10.00'),
            product_role=Ingredient.ProductRole.MAIN,
        )
        self.rice = Ingredient.objects.create(
            name='Rice',
            price_per_kg=Decimal('70.00'),
            customers_per_kg=Decimal('7.00'),
            product_role=Ingredient.ProductRole.STAPLE,
        )
        self.vegetables = Ingredient.objects.create(
            name='Vegetables',
            cost_per_customer=Decimal('6.00'),
            product_role=Ingredient.ProductRole.STAPLE,
        )

        self.ingredients_url = reverse('meals:ingredients-list')
        self.cycles_url = reverse('meals:cycles-list')
        self.plans_url = reverse('meals:cycle-plans-list')
        self.lines_url = reverse('meals:cycle-plan-lines-list')
        self.meals_url = reverse('meals:meals-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _create_april_plan(self):
        cycle = MealCycle.objects.create(year=2026, month=4)
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=self.meal,
            other_cost_percent=Decimal('30.00'),
            profit_percent=Decimal('20.00'),
        )
        return cycle, plan

    # --- Ingredients ---

    def test_admin_can_create_kg_ingredient(self):
        self._auth_admin()
        response = self.client.post(
            self.ingredients_url,
            {
                'name': 'Beef',
                'price_per_kg': '650.00',
                'customers_per_kg': '12.00',
                'pieces_per_kg': 70,
                'product_role': 'main',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['resolved_cost_per_customer'], '54.166667')

    def test_admin_can_create_flat_cost_ingredient(self):
        self._auth_admin()
        response = self.client.post(
            self.ingredients_url,
            {
                'name': 'Dhal+Cucumber',
                'cost_per_customer': '3.00',
                'product_role': 'staple',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['cost_per_customer'], '3.000000')

    def test_incomplete_pricing_rejected(self):
        self._auth_admin()
        response = self.client.post(
            self.ingredients_url,
            {'name': 'Broken', 'price_per_kg': '100.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_cannot_access_ingredient_api(self):
        self._auth_customer()
        response = self.client.get(self.ingredients_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_cannot_access_ingredient_api(self):
        response = self.client.get(self.ingredients_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Cycles ---

    def test_create_january_and_april_cycles(self):
        self._auth_admin()
        jan = self.client.post(self.cycles_url, {'year': 2026, 'month': 1}, format='json')
        apr = self.client.post(self.cycles_url, {'year': 2026, 'month': 4}, format='json')
        self.assertEqual(jan.status_code, status.HTTP_201_CREATED)
        self.assertEqual(jan.data['cycle_days'], 31)
        self.assertEqual(jan.data['total_meals'], 62)
        self.assertEqual(apr.status_code, status.HTTP_201_CREATED)
        self.assertEqual(apr.data['cycle_days'], 30)
        self.assertEqual(apr.data['total_meals'], 60)

    def test_duplicate_year_month_rejected(self):
        self._auth_admin()
        self.client.post(self.cycles_url, {'year': 2026, 'month': 4}, format='json')
        response = self.client.post(self.cycles_url, {'year': 2026, 'month': 4}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Plans / lines / summary / finalize ---

    def test_create_plan_with_meal_public_id(self):
        self._auth_admin()
        cycle = MealCycle.objects.create(year=2026, month=4)
        response = self.client.post(
            self.plans_url,
            {
                'cycle': cycle.id,
                'meal_public_id': str(self.meal.public_id),
                'other_cost_percent': '30.00',
                'profit_percent': '20.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meal_category'], self.meal.id)
        self.assertEqual(response.data['cycle'], cycle.id)
        self.assertNotIn('meal_public_id', response.data)

    def test_create_plan_unknown_meal_public_id_rejected(self):
        self._auth_admin()
        cycle = MealCycle.objects.create(year=2026, month=4)
        response = self.client.post(
            self.plans_url,
            {
                'cycle': cycle.id,
                'meal_public_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_public_id', response.data)

    def test_create_plan_without_meal_public_id_rejected(self):
        self._auth_admin()
        cycle = MealCycle.objects.create(year=2026, month=4)
        response = self.client.post(
            self.plans_url,
            {
                'cycle': cycle.id,
                'meal_category': self.meal.id,
                'other_cost_percent': '30.00',
                'profit_percent': '20.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_public_id', response.data)
        self.assertFalse(MealCyclePlan.objects.filter(cycle=cycle).exists())

    def test_create_plan_inactive_meal_public_id_rejected(self):
        self._auth_admin()
        cycle = MealCycle.objects.create(year=2026, month=4)
        inactive = MealCategory.objects.create(
            meal_name='Inactive Package',
            meal_type='monthly',
            meal_thumbnail=make_test_image('inactive.jpg'),
            is_active=False,
        )
        response = self.client.post(
            self.plans_url,
            {
                'cycle': cycle.id,
                'meal_public_id': str(inactive.public_id),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_public_id', response.data)

    def test_bulk_lines_summary_and_duplicate_rejection(self):
        self._auth_admin()
        _, plan = self._create_april_plan()
        replace_url = reverse('meals:cycle-plans-replace-lines', kwargs={'public_id': plan.public_id})
        response = self.client.put(
            replace_url,
            {
                'lines': [
                    {'ingredient': self.chicken.id, 'servings_count': 18},
                    {'ingredient': self.rice.id, 'servings_count': 60},
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        duplicate = self.client.post(
            self.lines_url,
            {'plan': plan.id, 'ingredient': self.chicken.id, 'servings_count': 1},
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        summary = self.client.get(reverse('meals:cycle-plans-summary', kwargs={'public_id': plan.public_id}))
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data['status'], 'draft')
        self.assertFalse(summary.data['using_snapshot'])
        self.assertEqual(len(summary.data['lines']), 2)

    def test_finalize_success_and_edit_blocked_then_reopen(self):
        self._auth_admin()
        _, plan = self._create_april_plan()
        replace_url = reverse('meals:cycle-plans-replace-lines', kwargs={'public_id': plan.public_id})
        self.client.put(
            replace_url,
            {
                'lines': [
                    {'ingredient': self.chicken.id, 'servings_count': 60},
                    {'ingredient': self.rice.id, 'servings_count': 60},
                    {'ingredient': self.vegetables.id, 'servings_count': 60},
                ]
            },
            format='json',
        )
        finalize = self.client.post(reverse('meals:cycle-plans-finalize', kwargs={'public_id': plan.public_id}))
        self.assertEqual(finalize.status_code, status.HTTP_200_OK)
        self.assertEqual(finalize.data['status'], 'finalized')
        self.assertTrue(finalize.data['using_snapshot'])
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.total_price, Decimal(finalize.data['total_cost']))
        self.assertEqual(finalize.data['published_meal_total_price'], str(self.meal.total_price))

        published_price = self.meal.total_price

        blocked = self.client.put(
            replace_url,
            {'lines': [{'ingredient': self.chicken.id, 'servings_count': 50}]},
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

        reopen = self.client.post(reverse('meals:cycle-plans-reopen', kwargs={'public_id': plan.public_id}))
        self.assertEqual(reopen.status_code, status.HTTP_200_OK)
        self.assertEqual(reopen.data['status'], 'draft')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.total_price, published_price)

        allowed = self.client.put(
            replace_url,
            {'lines': [{'ingredient': self.chicken.id, 'servings_count': 60}]},
            format='json',
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_finalize_fails_when_main_servings_mismatch(self):
        self._auth_admin()
        _, plan = self._create_april_plan()
        original_price = self.meal.total_price
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.chicken, servings_count=18)
        response = self.client.post(reverse('meals:cycle-plans-finalize', kwargs={'public_id': plan.public_id}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('main_servings_total', response.data)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.total_price, original_price)

    def test_finalized_snapshot_ignores_price_change(self):
        self._auth_admin()
        _, plan = self._create_april_plan()
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.chicken, servings_count=60)
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.rice, servings_count=60)
        finalize = self.client.post(reverse('meals:cycle-plans-finalize', kwargs={'public_id': plan.public_id}))
        original_rate = finalize.data['per_meal_rate']

        self.chicken.price_per_kg = Decimal('999.00')
        self.chicken.save(update_fields=['price_per_kg'])

        summary = self.client.get(reverse('meals:cycle-plans-summary', kwargs={'public_id': plan.public_id}))
        self.assertEqual(summary.data['per_meal_rate'], original_rate)
        self.assertTrue(summary.data['using_snapshot'])

    def test_public_meal_list_and_detail_offering(self):
        self._auth_admin()
        _, plan = self._create_april_plan()
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.chicken, servings_count=60)
        MealCyclePlanLine.objects.create(plan=plan, ingredient=self.rice, servings_count=60)
        self.client.post(reverse('meals:cycle-plans-finalize', kwargs={'public_id': plan.public_id}))
        self.client.credentials()

        list_response = self.client.get(self.meals_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        results = (
            list_response.data['results']
            if isinstance(list_response.data, dict) and 'results' in list_response.data
            else list_response.data
        )
        meal_row = next(item for item in results if item['public_id'] == str(self.meal.public_id))
        self.assertEqual(meal_row['pricing_status'], 'priced')
        self.assertNotIn('current_cycle_offering', meal_row)
        self.assertNotIn('price_per_kg', meal_row)
        self.assertNotIn('id', meal_row)

        detail = self.client.get(
            reverse('meals:meals-detail', kwargs={'public_id': self.meal.public_id})
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        offering = detail.data['current_cycle_offering']
        self.assertIsNotNone(offering)
        self.assertEqual(offering['year'], 2026)
        self.assertEqual(offering['month'], 4)
        self.assertEqual(offering['total_meals'], 60)
        self.assertIn('menu_items', offering)
        self.assertTrue(any(item['name'] == 'Chicken' for item in offering['menu_items']))
        self.assertNotIn('plan_id', offering)
        self.assertNotIn('product_cost', offering)
        self.assertNotIn('profit', offering)
        self.assertNotIn('other_cost', offering)
        for item in offering['menu_items']:
            self.assertNotIn('price_per_kg', item)
            self.assertNotIn('customers_per_kg', item)

    def test_public_list_shows_unpriced_meal(self):
        unpriced = MealCategory.objects.create(
            meal_name='Unpriced Plan',
            total_price=None,
            meal_type='monthly',
            meal_thumbnail=make_test_image('unpriced.jpg'),
        )
        response = self.client.get(self.meals_url)
        results = response.data['results'] if isinstance(response.data, dict) and 'results' in response.data else response.data
        row = next(item for item in results if item['public_id'] == str(unpriced.public_id))
        self.assertEqual(row['pricing_status'], 'unpriced')
        self.assertIsNone(row['total_price'])

    def test_recipes_endpoint_removed(self):
        self._auth_admin()
        response = self.client.get('/meals/recipes/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
