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

from meals.models import MealCategory
from meals.services.pricing import calculate_per_meal_price, get_present_month_days


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def make_large_image(name='large.jpg', size_mb=6):
    payload = b'0' * (size_mb * 1024 * 1024)
    return SimpleUploadedFile(name, payload, content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class MealAPITestCase(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.manager = User.objects.create_user(
            username='meal-admin',
            email='meal-admin@example.com',
            password='StrongPassword123',
        )
        self.manager.groups.add(self.admin_group)
        self.manager_token = Token.objects.create(user=self.manager)
        self.list_url = reverse('meals:meals-list')

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.manager_token.key}')

    def _meal_payload(self, **overrides):
        payload = {
            'meal_name': 'Chicken Rice Bowl',
            'meal_type': 'daily',
            'is_active': 'true',
            'meal_thumbnail': make_test_image(),
        }
        payload.update(overrides)
        return payload

    def test_create_meal_with_valid_data(self):
        self._auth()
        response = self.client.post(self.list_url, self._meal_payload(), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meal_name'], 'Chicken Rice Bowl')
        self.assertEqual(response.data['meal_type'], 'daily')
        self.assertEqual(response.data['meal_type_display'], 'Daily')
        self.assertTrue(response.data['is_active'])
        self.assertIn('meal_thumbnail', response.data)
        self.assertIsNone(response.data['total_price'])
        self.assertEqual(response.data['pricing_status'], 'unpriced')
        self.assertIsNone(response.data['per_meal_price'])
        self.assertIsNone(response.data.get('current_cycle_offering'))

    def test_create_meal_ignores_client_total_price(self):
        self._auth()
        response = self.client.post(
            self.list_url,
            self._meal_payload(total_price='999.00'),
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        meal = MealCategory.objects.get(pk=response.data['id'])
        self.assertIsNone(meal.total_price)
        self.assertEqual(response.data['pricing_status'], 'unpriced')

    def test_create_meal_fails_if_meal_type_invalid(self):
        self._auth()
        response = self.client.post(
            self.list_url,
            self._meal_payload(meal_type='invalid_type'),
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_type', response.data)

    def test_create_meal_fails_without_meal_thumbnail(self):
        self._auth()
        payload = self._meal_payload()
        del payload['meal_thumbnail']
        response = self.client.post(self.list_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_thumbnail', response.data)

    def test_create_meal_thumbnail_filename_uses_meal_name_and_datetime(self):
        self._auth()
        response = self.client.post(self.list_url, self._meal_payload(), format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        meal = MealCategory.objects.get(pk=response.data['id'])
        filename = meal.meal_thumbnail.name.split('/')[-1]
        self.assertRegex(filename, r'^chicken-rice-bowl-\d{8}-\d{6}(_[A-Za-z0-9]+)?\.jpg$')

    def test_list_meals_works(self):
        MealCategory.objects.create(
            meal_name='Beef Bowl',
            total_price=Decimal('200.00'),
            meal_type='weekly',
            meal_thumbnail=make_test_image('beef.jpg'),
        )
        response = self.client.get(self.list_url, {'search': 'Beef Bowl'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['meal_name'], 'Beef Bowl')
        expected_per_meal_price = calculate_per_meal_price(Decimal('200.00'))
        self.assertEqual(response.data[0]['per_meal_price'], str(expected_per_meal_price))

    def test_per_meal_price_uses_present_month_days(self):
        meal = MealCategory.objects.create(
            meal_name='Monthly Plan',
            total_price=Decimal('3100.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('monthly.jpg'),
        )
        response = self.client.get(reverse('meals:meals-detail', kwargs={'pk': meal.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_per_meal_price = calculate_per_meal_price(Decimal('3100.00'))
        self.assertEqual(response.data['per_meal_price'], str(expected_per_meal_price))

    def test_detail_meal_works(self):
        meal = MealCategory.objects.create(
            meal_name='Fish Curry',
            total_price=Decimal('150.00'),
            meal_type='monthly',
            meal_thumbnail=make_test_image('fish.jpg'),
        )
        response = self.client.get(reverse('meals:meals-detail', kwargs={'pk': meal.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['meal_name'], 'Fish Curry')
        self.assertEqual(response.data['meal_type_display'], 'Monthly')

    def test_update_meal_works(self):
        meal = MealCategory.objects.create(
            meal_name='Old Name',
            total_price=Decimal('120.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('old.jpg'),
        )
        self._auth()
        response = self.client.patch(
            reverse('meals:meals-detail', kwargs={'pk': meal.pk}),
            {'meal_name': 'Updated Name', 'total_price': '250.00'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meal.refresh_from_db()
        self.assertEqual(meal.meal_name, 'Updated Name')
        # total_price is not writable via meal APIs; published only via finalize
        self.assertEqual(str(meal.total_price), '120.00')
        self.assertEqual(response.data['pricing_status'], 'priced')

    def test_filter_by_meal_type_works(self):
        MealCategory.objects.create(
            meal_name='Daily Meal',
            total_price=Decimal('100.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('daily.jpg'),
        )
        MealCategory.objects.create(
            meal_name='Weekly Meal',
            total_price=Decimal('500.00'),
            meal_type='weekly',
            meal_thumbnail=make_test_image('weekly.jpg'),
        )
        response = self.client.get(self.list_url, {'meal_type': 'weekly'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['meal_name'], 'Weekly Meal')

    def test_filter_by_is_active_works(self):
        self._auth()
        active = MealCategory.objects.create(
            meal_name='Active Meal',
            total_price=Decimal('100.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('active.jpg'),
            is_active=True,
        )
        inactive = MealCategory.objects.create(
            meal_name='Inactive Meal',
            total_price=Decimal('100.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('inactive.jpg'),
            is_active=False,
        )
        self.client.credentials()
        response = self.client.get(self.list_url, {'is_active': 'false'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        self._auth()
        manager_response = self.client.get(self.list_url, {'is_active': 'false'})
        self.assertEqual(manager_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(manager_response.data), 1)
        self.assertEqual(manager_response.data[0]['id'], inactive.id)

    def test_search_by_meal_name_works(self):
        MealCategory.objects.create(
            meal_name='Chicken Rice Bowl',
            total_price=Decimal('180.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('chicken.jpg'),
        )
        MealCategory.objects.create(
            meal_name='Beef Steak',
            total_price=Decimal('300.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('beef2.jpg'),
        )
        response = self.client.get(self.list_url, {'search': 'chicken'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['meal_name'], 'Chicken Rice Bowl')

    def test_invalid_image_extension_fails(self):
        self._auth()
        invalid_file = SimpleUploadedFile('meal.gif', b'gif-content', content_type='image/gif')
        response = self.client.post(
            self.list_url,
            self._meal_payload(meal_thumbnail=invalid_file),
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_thumbnail', response.data)

    def test_image_larger_than_5mb_fails(self):
        self._auth()
        response = self.client.post(
            self.list_url,
            self._meal_payload(meal_thumbnail=make_large_image()),
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('meal_thumbnail', response.data)

    def test_soft_delete_sets_is_active_false(self):
        meal = MealCategory.objects.create(
            meal_name='Delete Me',
            total_price=Decimal('100.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('delete.jpg'),
        )
        self._auth()
        response = self.client.delete(reverse('meals:meals-detail', kwargs={'pk': meal.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        meal.refresh_from_db()
        self.assertFalse(meal.is_active)

    def test_public_list_only_shows_active_meals(self):
        MealCategory.objects.create(
            meal_name='Visible Meal',
            total_price=Decimal('100.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('visible.jpg'),
            is_active=True,
        )
        MealCategory.objects.create(
            meal_name='Hidden Meal',
            total_price=Decimal('100.00'),
            meal_type='daily',
            meal_thumbnail=make_test_image('hidden.jpg'),
            is_active=False,
        )
        response = self.client.get(self.list_url, {'search': 'Visible Meal'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['meal_name'], 'Visible Meal')
