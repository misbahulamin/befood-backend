from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile
from user_management.services.profile_picture import (
    build_profile_folder_slug,
    profile_picture_upload_path,
    upload_profile_picture,
)


def make_test_image(name='avatar.jpg', size=(40, 40), color='red', fmt='JPEG'):
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format=fmt)
    buffer.seek(0)
    content_type = {
        'JPEG': 'image/jpeg',
        'PNG': 'image/png',
        'WEBP': 'image/webp',
    }.get(fmt, 'image/jpeg')
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


@override_settings(
    MEDIA_ROOT='test_media_profile_pictures',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ProfilePicturePathTests(APITestCase):
    def test_named_user_folder_slug(self):
        user = User(first_name='Abdul', last_name='Rahim', email='x@example.com')
        profile = CustomerProfile(user=user)
        profile.public_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        slug = build_profile_folder_slug(user, profile.public_id)
        self.assertEqual(slug, 'abdul_rahim_aaaaaaaa')

    def test_email_local_part_when_no_name(self):
        user = User(first_name='', last_name='', email='rahim123@gmail.com')
        profile = CustomerProfile(user=user)
        profile.public_id = '11111111-2222-3333-4444-555555555555'
        slug = build_profile_folder_slug(user, profile.public_id)
        self.assertEqual(slug, 'rahim123_11111111')

    def test_collision_safe_distinct_public_ids(self):
        user_a = User(first_name='John', last_name='Doe', email='a@example.com')
        user_b = User(first_name='John', last_name='Doe', email='b@example.com')
        slug_a = build_profile_folder_slug(user_a, 'aaaaaaaa-0000-0000-0000-000000000001')
        slug_b = build_profile_folder_slug(user_b, 'bbbbbbbb-0000-0000-0000-000000000002')
        self.assertNotEqual(slug_a, slug_b)
        self.assertTrue(slug_a.startswith('john_doe_'))
        self.assertTrue(slug_b.startswith('john_doe_'))

    def test_upload_path_prefix_and_filename(self):
        user = User.objects.create_user(
            username='pathuser',
            email='pathuser@example.com',
            password='StrongPassword123',
            first_name='Abdul',
            last_name='Rahim',
        )
        profile = CustomerProfile.objects.create(
            user=user,
            phone='1710000001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
        )
        path = profile_picture_upload_path(profile, 'photo.JPEG')
        self.assertTrue(path.startswith('profiles/users/'))
        self.assertTrue(path.endswith('/profile_picture.jpeg'))
        self.assertIn('abdul_rahim_', path)


@override_settings(
    MEDIA_ROOT='test_media_profile_pictures',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class CustomerProfilePictureAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='picustomer',
            email='picustomer@example.com',
            password='StrongPassword123',
            first_name='Abdul',
            last_name='Rahim',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1710000099',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.upload_url = reverse('user_management:customer-profile-image')
        self.profile_url = reverse('user_management:customer-profile')

    def test_authenticated_upload_success(self):
        image = make_test_image('face.jpg')
        response = self.client.post(self.upload_url, {'image': image}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile_image_url', response.data)
        self.assertTrue(response.data['profile_image_url'])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.profile_picture)
        self.assertIn('profiles/users/', self.profile.profile_picture.name)
        self.assertIn('profile_picture.', self.profile.profile_picture.name)

        get_response = self.client.get(self.profile_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            get_response.data['customer_profile']['profile_image_url'],
            response.data['profile_image_url'],
        )
        self.assertEqual(get_response.data['profile_image_url'], response.data['profile_image_url'])

    def test_unauthenticated_upload_denied(self):
        self.client.credentials()
        image = make_test_image('face.jpg')
        response = self.client.post(self.upload_url, {'image': image}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_extension_rejected(self):
        bad = SimpleUploadedFile('face.gif', b'gif-content', content_type='image/gif')
        response = self.client.post(self.upload_url, {'image': bad}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)

    def test_oversized_rejected(self):
        # Valid JPEG header content but oversized payload for size check.
        big = SimpleUploadedFile(
            'big.jpg',
            b'\xff\xd8\xff' + (b'0' * (2 * 1024 * 1024 + 10)),
            content_type='image/jpeg',
        )
        response = self.client.post(self.upload_url, {'image': big}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('image', response.data)

    def test_replace_and_clear(self):
        first = make_test_image('one.jpg', color='blue')
        upload1 = self.client.post(self.upload_url, {'image': first}, format='multipart')
        self.assertEqual(upload1.status_code, status.HTTP_200_OK)

        second = make_test_image('two.jpg', color='green')
        upload2 = self.client.post(self.upload_url, {'image': second}, format='multipart')
        self.assertEqual(upload2.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.profile_picture)
        self.assertIn('profiles/users/', self.profile.profile_picture.name)
        self.assertIn('profile_picture.', self.profile.profile_picture.name.split('/')[-1])
        # Previous object should no longer be referenced (same logical key is OK).
        self.assertEqual(
            self.profile.profile_picture.name.split('/')[-1].split('.')[0],
            'profile_picture',
        )

        clear = self.client.patch(
            self.profile_url,
            {'profile_image_url': None},
            format='json',
        )
        self.assertEqual(clear.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)
        self.assertIsNone(clear.data['customer_profile']['profile_image_url'])

    def test_patch_data_url_does_not_set_picture(self):
        response = self.client.patch(
            self.profile_url,
            {'profile_image_url': 'data:image/png;base64,aaa'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)


@override_settings(
    MEDIA_ROOT='test_media_profile_pictures',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AdminCustomerProfilePictureTests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin = User.objects.create_user(
            username='admin-pic',
            email='admin-pic@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin, is_verified=True)
        self.admin.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin)

        self.customer_user = User.objects.create_user(
            username='cust-pic',
            email='cust-pic@example.com',
            password='StrongPassword123',
            first_name='Alice',
            last_name='Active',
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1711111199',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        upload_profile_picture(self.customer, make_test_image('admin-avatar.jpg'))
        self.list_url = reverse('web_customers:admin-customer-list')
        self.detail_url = reverse(
            'web_customers:admin-customer-detail',
            kwargs={'public_id': self.customer.public_id},
        )

    def test_admin_list_and_overview_return_picture_url(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        list_response = self.client.get(self.list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        row = next(
            item
            for item in list_response.data['results']
            if item['email'] == 'cust-pic@example.com'
        )
        self.assertIsNotNone(row['profile_picture_url'])
        self.assertIn('profiles/users/', row['profile_picture_url'])

        detail = self.client.get(self.detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(detail.data['profile_picture_url'])
        self.assertIsNotNone(detail.data['summary']['profile_picture_url'])
