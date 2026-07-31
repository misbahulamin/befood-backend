from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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
from orders.models import Order, OrderWalletSettings
from orders.services.meal_month import (
    MealMonthValidationError,
    assert_meal_month_in_window,
    iter_orderable_months,
    resolve_optional_year_month,
)
from orders.services.order_duration import calculate_order_period
from orders.services.order_service import (
    InsufficientWalletBalanceError,
    InvalidMealMonthError,
    MenuNotPublishedError,
    MonthLockError,
    create_meal_order,
)
from user_management.models import CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _set_wallet_min(amount: Decimal) -> OrderWalletSettings:
    settings_obj = OrderWalletSettings.load()
    settings_obj.min_wallet_balance_to_order = amount
    settings_obj.save()
    return settings_obj


@override_settings(MEDIA_ROOT='test_media')
class MealMonthHelperTests(TestCase):
    def test_resolve_optional_both_omitted(self):
        self.assertIsNone(resolve_optional_year_month(None, None))

    def test_resolve_optional_partial_rejected(self):
        with self.assertRaises(MealMonthValidationError):
            resolve_optional_year_month(2026, None)
        with self.assertRaises(MealMonthValidationError):
            resolve_optional_year_month(None, 7)

    def test_window_bounds(self):
        today = date(2026, 7, 15)
        assert_meal_month_in_window(2026, 7, today=today)
        assert_meal_month_in_window(2027, 7, today=today)
        with self.assertRaises(MealMonthValidationError):
            assert_meal_month_in_window(2026, 6, today=today)
        with self.assertRaises(MealMonthValidationError):
            assert_meal_month_in_window(2027, 8, today=today)

    def test_iter_orderable_months_has_thirteen(self):
        months = list(iter_orderable_months(today=date(2026, 7, 31)))
        self.assertEqual(len(months), 13)
        self.assertEqual(months[0], (2026, 7))
        self.assertEqual(months[-1], (2027, 7))

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    def test_period_current_vs_future_monthly(self, _mock):
        current = calculate_order_period(
            MealCategory.MealType.MONTHLY,
            target_year=2026,
            target_month=7,
        )
        self.assertEqual(current.order_month, '2026-07')
        self.assertEqual(current.start_date, date(2026, 7, 1))
        self.assertEqual(current.end_date, date(2026, 7, 31))

        future = calculate_order_period(
            MealCategory.MealType.MONTHLY,
            target_year=2026,
            target_month=8,
        )
        self.assertEqual(future.order_month, '2026-08')
        self.assertEqual(future.start_date, date(2026, 8, 1))
        self.assertEqual(future.end_date, date(2026, 8, 31))
        self.assertEqual(future.service_days_count, monthrange(2026, 8)[1])


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class FutureMonthOrderAPITests(APITestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='future_month_customer',
            email='future_month@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.user.groups.add(group)
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712999001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        _set_wallet_min(Decimal('0.00'))
        self.meal = MealCategory.objects.create(
            meal_name='Future Month Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('future.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )
        self.chicken = Ingredient.objects.create(
            name='Chicken FM',
            price_per_kg=Decimal('130.00'),
            customers_per_kg=Decimal('10.00'),
        )
        self.beef = Ingredient.objects.create(
            name='Beef FM',
            price_per_kg=Decimal('650.00'),
            customers_per_kg=Decimal('12.00'),
        )
        self.rice = Ingredient.objects.create(
            name='Rice FM',
            price_per_kg=Decimal('70.00'),
            customers_per_kg=Decimal('7.00'),
        )
        self.create_url = reverse('orders:order-list')
        self.orderable_url = reverse('orders:order-orderable-months')
        self.preview_url = reverse('meals:order-menu-preview')
        self.package_menu_url = reverse('meals:my-package-menu')

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def _fund(self, amount: Decimal):
        wallet = get_or_create_wallet(self.profile)
        if amount > 0:
            credit_wallet(wallet, amount)
        return wallet

    def _create_published_schedule(self, year, month):
        cycle, _ = MealCycle.objects.get_or_create(year=year, month=month)
        plan = MealCyclePlan.objects.create(cycle=cycle, meal_category=self.meal)
        total = cycle.total_meals
        half = total // 2
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.chicken,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=half,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.beef,
            product_role=MealCyclePlanLine.ProductRole.MAIN,
            servings_count=total - half,
        )
        MealCyclePlanLine.objects.create(
            plan=plan,
            ingredient=self.rice,
            product_role=MealCyclePlanLine.ProductRole.STAPLE,
            servings_count=total,
        )
        finalize_plan(plan)
        keys = expected_slot_keys(year, month)
        chicken_keys, beef_keys = keys[:half], keys[half:]
        assignments = []
        for key in chicken_keys:
            assignments.append(
                {
                    'service_date': key[0].isoformat(),
                    'meal_period': key[1],
                    'ingredient_ids': [self.chicken.id, self.rice.id],
                }
            )
        for key in beef_keys:
            assignments.append(
                {
                    'service_date': key[0].isoformat(),
                    'meal_period': key[1],
                    'ingredient_ids': [self.beef.id, self.rice.id],
                }
            )
        schedule = MonthlyMenuSchedule.objects.create(plan=plan)
        replace_schedule_assignments(schedule, assignments)
        return publish_schedule(schedule)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 15))
    def test_create_future_published_month(self, *_mocks):
        self._create_published_schedule(2026, 8)
        self._auth()
        response = self.client.post(
            self.create_url,
            {
                'meal_public_id': str(self.meal.public_id),
                'year': 2026,
                'month': 8,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['order_month'], '2026-08')
        self.assertEqual(response.data['order_start_date'], '2026-08-01')
        self.assertEqual(response.data['order_end_date'], '2026-08-31')

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 15))
    def test_create_omit_year_month_current(self, *_mocks):
        self._create_published_schedule(2026, 7)
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['order_month'], '2026-07')

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 15))
    def test_reject_past_and_beyond_horizon(self, *_mocks):
        self._auth()
        past = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 6},
            format='json',
        )
        self.assertEqual(past.status_code, status.HTTP_400_BAD_REQUEST)

        far = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2027, 'month': 8},
            format='json',
        )
        self.assertEqual(far.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_partial_year_month(self):
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 15))
    def test_unpublished_rejects_create(self, *_mocks):
        self._auth()
        response = self.client.post(
            self.create_url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 8},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not been published', str(response.data))
        self.assertEqual(Order.objects.count(), 0)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 15))
    def test_month_lock_and_wallet_and_other_month(self, *_mocks):
        self._create_published_schedule(2026, 7)
        self._create_published_schedule(2026, 8)
        july = create_meal_order(self.profile, self.meal, year=2026, month=7)
        self.assertEqual(july.order_month, '2026-07')

        with self.assertRaises(MonthLockError):
            create_meal_order(self.profile, self.meal, year=2026, month=7)

        august = create_meal_order(self.profile, self.meal, year=2026, month=8)
        self.assertEqual(august.order_month, '2026-08')

        self._create_published_schedule(2026, 9)
        _set_wallet_min(Decimal('500.00'))
        with self.assertRaises(InsufficientWalletBalanceError):
            create_meal_order(self.profile, self.meal, year=2026, month=9)

    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 15))
    def test_orderable_months(self, _mock):
        self._create_published_schedule(2026, 7)
        Order.objects.create(
            customer=self.profile,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_type_snapshot=self.meal.meal_type,
            meal_period_snapshot=self.meal.meal_period,
            total_price_snapshot=self.meal.total_price,
            per_meal_price_snapshot=Decimal('50.00'),
            order_status=Order.OrderStatus.CONFIRMED,
            order_start_date=date(2026, 7, 1),
            order_end_date=date(2026, 7, 31),
            service_days_count=31,
            order_month='2026-07',
        )
        self._auth()
        response = self.client.get(
            self.orderable_url,
            {'meal_public_id': str(self.meal.public_id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['months']), 13)
        self.assertTrue(response.data['months'][0]['is_current'])
        self.assertTrue(response.data['months'][0]['is_published'])
        self.assertTrue(response.data['months'][0]['has_order'])
        self.assertFalse(response.data['months'][1]['is_published'])

        unauth = self.client
        unauth.credentials()
        bare = unauth.get(self.orderable_url, {'meal_public_id': str(self.meal.public_id)})
        self.assertEqual(bare.status_code, status.HTTP_401_UNAUTHORIZED)

        self._auth()
        missing = self.client.get(self.orderable_url, {'meal_public_id': str(uuid4())})
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    @patch('django.utils.timezone.localdate', return_value=date(2026, 7, 15))
    def test_order_menu_preview(self, _mock):
        self._create_published_schedule(2026, 8)
        self._auth()
        published = self.client.get(
            self.preview_url,
            {
                'meal_public_id': str(self.meal.public_id),
                'year': 2026,
                'month': 8,
            },
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertTrue(published.data['schedule_published'])
        self.assertGreater(len(published.data['days']), 0)

        unpublished = self.client.get(
            self.preview_url,
            {
                'meal_public_id': str(self.meal.public_id),
                'year': 2026,
                'month': 9,
            },
        )
        self.assertEqual(unpublished.status_code, status.HTTP_200_OK)
        self.assertFalse(unpublished.data['schedule_published'])
        self.assertEqual(unpublished.data['days'], [])

        bad = self.client.get(
            self.preview_url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026},
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        missing = self.client.get(self.preview_url, {'meal_public_id': str(uuid4())})
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

        package = self.client.get(self.package_menu_url, {'year': 2026, 'month': 8})
        self.assertEqual(package.status_code, status.HTTP_200_OK)
        self.assertEqual(package.data['packages'], [])

        self.client.credentials()
        unauth = self.client.get(
            self.preview_url,
            {'meal_public_id': str(self.meal.public_id), 'year': 2026, 'month': 8},
        )
        self.assertEqual(unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_service_invalid_month_error(self):
        with self.assertRaises(InvalidMealMonthError):
            create_meal_order(self.profile, self.meal, year=2020, month=1)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 15))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 15))
    def test_service_menu_not_published_error(self, *_mocks):
        with self.assertRaises(MenuNotPublishedError):
            create_meal_order(self.profile, self.meal, year=2026, month=8)
