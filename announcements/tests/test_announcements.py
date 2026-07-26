from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile

from announcements.api.views import ActiveAnnouncementViewSet, AnnouncementViewSet
from announcements.models import Announcement
from announcements.services import compute_lifecycle_status, get_active_announcements

User = get_user_model()


def make_test_image(name='banner.jpg', size=(100, 100), color='blue'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _make_announcement(**overrides) -> Announcement:
    defaults = {
        'title': 'Summer Offer',
        'description': 'Get 10% off',
        'type': Announcement.AnnouncementType.OFFER,
        'severity': Announcement.Severity.SUCCESS,
        'is_published': True,
        'priority': 0,
    }
    defaults.update(overrides)
    announcement = Announcement(**defaults)
    announcement.full_clean()
    announcement.save()
    return announcement


class AnnouncementModelValidationTests(TestCase):
    def test_rejects_blank_title(self):
        announcement = Announcement(title='   ', is_published=False)
        with self.assertRaises(ValidationError) as ctx:
            announcement.full_clean()
        self.assertIn('title', ctx.exception.message_dict)

    def test_rejects_invalid_type(self):
        announcement = Announcement(title='Bad', type='promo')
        with self.assertRaises(ValidationError) as ctx:
            announcement.full_clean()
        self.assertIn('type', ctx.exception.message_dict)

    def test_rejects_invalid_severity(self):
        announcement = Announcement(title='Bad', severity='critical')
        with self.assertRaises(ValidationError) as ctx:
            announcement.full_clean()
        self.assertIn('severity', ctx.exception.message_dict)

    def test_rejects_publish_until_not_after_publish_at(self):
        now = timezone.now()
        announcement = Announcement(
            title='Window',
            publish_at=now,
            publish_until=now,
        )
        with self.assertRaises(ValidationError) as ctx:
            announcement.full_clean()
        self.assertIn('publish_until', ctx.exception.message_dict)

    def test_rejects_button_text_without_url(self):
        announcement = Announcement(
            title='CTA',
            button_text='Order Now',
            button_url='',
        )
        with self.assertRaises(ValidationError) as ctx:
            announcement.full_clean()
        self.assertIn('button_url', ctx.exception.message_dict)

    def test_accepts_valid_cta_pair(self):
        announcement = Announcement(
            title='CTA',
            button_text='Order Now',
            button_url='https://befood.example/order',
        )
        announcement.full_clean()
        announcement.save()
        self.assertTrue(Announcement.objects.filter(pk=announcement.pk).exists())


class ActiveAnnouncementServiceTests(TestCase):
    def test_draft_hidden(self):
        _make_announcement(is_published=False, title='Draft')
        self.assertEqual(get_active_announcements().count(), 0)
        self.assertEqual(
            compute_lifecycle_status(Announcement.objects.get()),
            'draft',
        )

    def test_future_publish_at_hidden(self):
        now = timezone.now()
        announcement = _make_announcement(publish_at=now + timedelta(days=1))
        self.assertEqual(get_active_announcements(at=now).count(), 0)
        self.assertEqual(
            compute_lifecycle_status(announcement, at=now),
            'scheduled',
        )

    def test_past_publish_until_hidden(self):
        now = timezone.now()
        announcement = _make_announcement(
            publish_until=now - timedelta(minutes=1),
        )
        self.assertEqual(get_active_announcements(at=now).count(), 0)
        self.assertEqual(
            compute_lifecycle_status(announcement, at=now),
            'expired',
        )

    def test_inclusive_publish_until_boundary_visible(self):
        now = timezone.now()
        announcement = _make_announcement(publish_until=now)
        qs = get_active_announcements(at=now)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, announcement.pk)
        self.assertEqual(compute_lifecycle_status(announcement, at=now), 'active')

    def test_open_ended_published_visible(self):
        announcement = _make_announcement(publish_at=None, publish_until=None)
        qs = get_active_announcements()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, announcement.pk)
        self.assertEqual(compute_lifecycle_status(announcement), 'active')

    def test_priority_descending_then_newest(self):
        older_high = _make_announcement(title='Older high', priority=10)
        newer_high = _make_announcement(title='Newer high', priority=10)
        low = _make_announcement(title='Low', priority=1)
        ids = list(get_active_announcements().values_list('pk', flat=True))
        self.assertEqual(ids, [newer_high.pk, older_high.pk, low.pk])


@override_settings(ROOT_URLCONF='core.urls', MEDIA_ROOT='test_media')
class ActiveAnnouncementAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('announcements:active-list')

    def test_anonymous_200_lists_active(self):
        _make_announcement(
            title='Hello',
            description='World',
            type=Announcement.AnnouncementType.NOTICE,
            severity=Announcement.Severity.WARNING,
            button_text='Subscribe',
            button_url='https://befood.example/subscribe',
            priority=5,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row['title'], 'Hello')
        self.assertEqual(row['description'], 'World')
        self.assertEqual(row['type'], 'notice')
        self.assertEqual(row['severity'], 'warning')
        self.assertEqual(row['button_text'], 'Subscribe')
        self.assertEqual(row['button_url'], 'https://befood.example/subscribe')
        self.assertEqual(row['priority'], 5)
        self.assertIn('public_id', row)
        self.assertIn('image', row)
        self.assertNotIn('is_published', row)

    def test_empty_active_set(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_drafts_and_expired_omitted(self):
        now = timezone.now()
        _make_announcement(title='Draft', is_published=False)
        _make_announcement(
            title='Expired',
            publish_until=now - timedelta(seconds=1),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_pagination_caps_page_size(self):
        for i in range(3):
            _make_announcement(title=f'N{i}', priority=i)
        response = self.client.get(self.url, {'page_size': 999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
        self.assertLessEqual(len(response.data['results']), 50)


@override_settings(ROOT_URLCONF='core.urls', MEDIA_ROOT='test_media')
class AnnouncementAdminAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='announcement-admin',
            email='announcement-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='announcement-customer',
            email='announcement-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345688',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.list_url = reverse('announcements:announcements-list')
        self.active_url = reverse('announcements:active-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _detail_url(self, public_id):
        return reverse(
            'announcements:announcements-detail',
            kwargs={'public_id': public_id},
        )

    def test_url_resolution_active_before_admin_detail(self):
        active_match = resolve('/announcements/active/')
        self.assertEqual(active_match.func.cls, ActiveAnnouncementViewSet)

        announcement = _make_announcement(title='Route probe', is_published=False)
        detail_match = resolve(f'/announcements/{announcement.public_id}/')
        self.assertEqual(detail_match.func.cls, AnnouncementViewSet)

        list_match = resolve('/announcements/')
        self.assertEqual(list_match.func.cls, AnnouncementViewSet)

    def test_anonymous_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        create = self.client.post(
            self.list_url,
            {'title': 'Nope', 'is_published': False},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_crud_publish_and_delete(self):
        self._auth_admin()
        create_resp = self.client.post(
            self.list_url,
            {
                'title': 'New Package Launch',
                'description': 'Try the premium plan.',
                'type': 'new_package',
                'severity': 'info',
                'is_published': False,
                'priority': 2,
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        public_id = create_resp.data['public_id']
        self.assertEqual(create_resp.data['lifecycle_status'], 'draft')
        self.assertFalse(create_resp.data['is_published'])
        self.assertIsNone(create_resp.data['image'])

        public_feed = self.client.get(self.active_url)
        self.assertEqual(public_feed.status_code, status.HTTP_200_OK)
        self.assertEqual(public_feed.data['results'], [])

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data['count'], 1)

        detail_resp = self.client.get(self._detail_url(public_id))
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['title'], 'New Package Launch')
        self.assertIn('lifecycle_status', detail_resp.data)

        patch_resp = self.client.patch(
            self._detail_url(public_id),
            {'is_published': True},
            format='json',
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(patch_resp.data['is_published'])
        self.assertEqual(patch_resp.data['lifecycle_status'], 'active')

        public_after = self.client.get(self.active_url)
        self.assertEqual(public_after.status_code, status.HTTP_200_OK)
        self.assertEqual(len(public_after.data['results']), 1)
        self.assertEqual(public_after.data['results'][0]['public_id'], public_id)

        delete_resp = self.client.delete(self._detail_url(public_id))
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Announcement.objects.filter(public_id=public_id).exists())

    def test_multipart_image_upload(self):
        self._auth_admin()
        create_resp = self.client.post(
            self.list_url,
            {
                'title': 'Banner Promo',
                'type': 'offer',
                'severity': 'success',
                'is_published': True,
                'priority': '1',
                'image': make_test_image(),
            },
            format='multipart',
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(create_resp.data['image'])
        public_id = create_resp.data['public_id']
        announcement = Announcement.objects.get(public_id=public_id)
        self.assertTrue(announcement.image)

        patch_resp = self.client.patch(
            self._detail_url(public_id),
            {'image': make_test_image('banner2.jpg', color='green')},
            format='multipart',
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(patch_resp.data['image'])

    def test_validation_cta_and_schedule(self):
        self._auth_admin()
        bad_cta = self.client.post(
            self.list_url,
            {
                'title': 'CTA missing URL',
                'button_text': 'Order Now',
                'button_url': '',
                'is_published': False,
            },
            format='json',
        )
        self.assertEqual(bad_cta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('button_url', bad_cta.data)

        now = timezone.now()
        bad_window = self.client.post(
            self.list_url,
            {
                'title': 'Window',
                'publish_at': now.isoformat().replace('+00:00', 'Z'),
                'publish_until': now.isoformat().replace('+00:00', 'Z'),
                'is_published': False,
            },
            format='json',
        )
        self.assertEqual(bad_window.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('publish_until', bad_window.data)
        self.assertEqual(Announcement.objects.count(), 0)

    def test_filters_and_lifecycle_status(self):
        self._auth_admin()
        now = timezone.now()
        draft = _make_announcement(
            title='Draft A',
            is_published=False,
            type='notice',
            severity='info',
        )
        offer = _make_announcement(
            title='Live Offer',
            is_published=True,
            type='offer',
            severity='success',
        )
        expired = _make_announcement(
            title='Expired B',
            is_published=True,
            type='notice',
            severity='info',
            publish_until=now - timedelta(minutes=1),
        )

        published = self.client.get(self.list_url, {'is_published': 'true'})
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        published_ids = {row['public_id'] for row in published.data['results']}
        self.assertEqual(
            published_ids,
            {str(offer.public_id), str(expired.public_id)},
        )

        offers = self.client.get(self.list_url, {'type': 'offer'})
        self.assertEqual(offers.status_code, status.HTTP_200_OK)
        self.assertEqual(len(offers.data['results']), 1)
        self.assertEqual(offers.data['results'][0]['public_id'], str(offer.public_id))

        search = self.client.get(self.list_url, {'search': 'Draft'})
        self.assertEqual(search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(search.data['results']), 1)
        self.assertEqual(search.data['results'][0]['public_id'], str(draft.public_id))

        draft_detail = self.client.get(self._detail_url(draft.public_id))
        self.assertEqual(draft_detail.data['lifecycle_status'], 'draft')

        expired_detail = self.client.get(self._detail_url(expired.public_id))
        self.assertEqual(expired_detail.data['lifecycle_status'], 'expired')

        offer_detail = self.client.get(self._detail_url(offer.public_id))
        self.assertEqual(offer_detail.data['lifecycle_status'], 'active')
