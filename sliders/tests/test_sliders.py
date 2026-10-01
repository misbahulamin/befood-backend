from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile

from sliders.models import HomeSlider

User = get_user_model()


def make_test_image(name='banner.jpg', size=(80, 40), color='blue', fmt='JPEG'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format=fmt)
    buffer.seek(0)
    content_type = {
        'JPEG': 'image/jpeg',
        'PNG': 'image/png',
        'WEBP': 'image/webp',
    }.get(fmt, 'image/jpeg')
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


def _make_slider(**overrides) -> HomeSlider:
    image = overrides.pop('image', None) or make_test_image()
    slider = HomeSlider(image=image, **overrides)
    slider.save()
    return slider


@override_settings(ROOT_URLCONF='core.urls', MEDIA_ROOT='test_media_sliders')
class HomeSliderModelOrderTests(APITestCase):
    def test_priority_ascending_then_created_at(self):
        third = _make_slider(priority=3)
        first = _make_slider(priority=1)
        second = _make_slider(priority=2)
        ids = list(HomeSlider.objects.values_list('id', flat=True))
        self.assertEqual(ids, [first.id, second.id, third.id])

    def test_duplicate_priority_earlier_created_first(self):
        older = _make_slider(priority=1)
        newer = _make_slider(priority=1)
        ids = list(HomeSlider.objects.filter(priority=1).values_list('id', flat=True))
        self.assertEqual(ids, [older.id, newer.id])


@override_settings(ROOT_URLCONF='core.urls', MEDIA_ROOT='test_media_sliders')
class PublicSliderAPITests(APITestCase):
    def setUp(self):
        self.url = '/sliders/'

    def test_empty_feed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_active_only_ordered_and_cache_header(self):
        _make_slider(priority=2)
        first = _make_slider(priority=1)
        _make_slider(priority=1, is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Cache-Control'), 'public, max-age=300')
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['priority'], 1)
        self.assertEqual(response.data[0]['public_id'], str(first.public_id))
        self.assertEqual(response.data[1]['priority'], 2)
        self.assertTrue(response.data[0]['image_url'].startswith('http'))
        self.assertNotIn('is_active', response.data[0])

    def test_anonymous_allowed(self):
        _make_slider(priority=1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@override_settings(ROOT_URLCONF='core.urls', MEDIA_ROOT='test_media_sliders')
class AdminSliderAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='slider-admin',
            email='slider-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='slider-customer',
            email='slider-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345699',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.list_url = '/sliders/admin/'

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _detail_url(self, public_id):
        return f'/sliders/admin/{public_id}/'

    def test_anonymous_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_requires_image(self):
        self._auth_admin()
        response = self.client.post(
            self.list_url,
            {'priority': 1, 'is_active': True},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)
        self.assertEqual(HomeSlider.objects.count(), 0)

    def test_invalid_type_rejected(self):
        self._auth_admin()
        bogus = SimpleUploadedFile('notes.txt', b'not-an-image', content_type='text/plain')
        response = self.client.post(
            self.list_url,
            {'priority': 1, 'image': bogus},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(HomeSlider.objects.count(), 0)

    def test_oversize_rejected(self):
        self._auth_admin()
        too_big = SimpleUploadedFile(
            'huge.jpg',
            b'0' * (5 * 1024 * 1024 + 1),
            content_type='image/jpeg',
        )
        response = self.client.post(
            self.list_url,
            {'priority': 1, 'image': too_big},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(HomeSlider.objects.count(), 0)

    def test_admin_crud_toggle_and_absolute_url(self):
        self._auth_admin()
        create_resp = self.client.post(
            self.list_url,
            {
                'priority': 2,
                'is_active': True,
                'image': make_test_image(),
            },
            format='multipart',
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        public_id = create_resp.data['public_id']
        self.assertEqual(create_resp.data['priority'], 2)
        self.assertTrue(create_resp.data['is_active'])
        self.assertTrue(create_resp.data['image_url'].startswith('http'))

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data['count'], 1)

        patch_resp = self.client.patch(
            self._detail_url(public_id),
            {'is_active': False},
            format='json',
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(patch_resp.data['is_active'])
        self.assertTrue(HomeSlider.objects.filter(public_id=public_id).exists())

        public_feed = self.client.get('/sliders/')
        self.assertEqual(public_feed.status_code, status.HTTP_200_OK)
        self.assertEqual(public_feed.data, [])

        delete_resp = self.client.delete(self._detail_url(public_id))
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(HomeSlider.objects.filter(public_id=public_id).exists())
