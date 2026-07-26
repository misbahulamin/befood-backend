from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile

from notices.api.views import ActiveNoticeViewSet, NoticeViewSet
from notices.models import Notice
from notices.services import compute_lifecycle_status, get_active_notices

User = get_user_model()


def _make_notice(**overrides) -> Notice:
    defaults = {
        'title_en': 'Holiday hours',
        'title_bn': 'ছুটির সময়সূচি',
        'body_en': 'We are closed tomorrow.',
        'body_bn': 'আগামীকাল বন্ধ থাকব।',
        'severity': Notice.Severity.INFO,
        'is_published': True,
        'sort_order': 0,
    }
    defaults.update(overrides)
    notice = Notice(**defaults)
    notice.full_clean()
    notice.save()
    return notice


class NoticeModelValidationTests(TestCase):
    def test_rejects_empty_titles_in_both_locales(self):
        notice = Notice(
            title_en='',
            title_bn='',
            body_en='x',
            is_published=False,
        )
        with self.assertRaises(ValidationError) as ctx:
            notice.full_clean()
        self.assertIn('title_en', ctx.exception.message_dict)
        self.assertIn('title_bn', ctx.exception.message_dict)

    def test_accepts_english_title_only(self):
        notice = Notice(title_en='Only EN', title_bn='', is_published=False)
        notice.full_clean()
        notice.save()
        self.assertTrue(Notice.objects.filter(pk=notice.pk).exists())

    def test_rejects_invalid_severity(self):
        notice = Notice(title_en='Bad', severity='urgent')
        with self.assertRaises(ValidationError) as ctx:
            notice.full_clean()
        self.assertIn('severity', ctx.exception.message_dict)

    def test_rejects_publish_until_not_after_publish_at(self):
        now = timezone.now()
        notice = Notice(
            title_en='Window',
            publish_at=now,
            publish_until=now,
        )
        with self.assertRaises(ValidationError) as ctx:
            notice.full_clean()
        self.assertIn('publish_until', ctx.exception.message_dict)

    def test_accepts_publish_until_after_publish_at(self):
        now = timezone.now()
        notice = Notice(
            title_en='Window',
            publish_at=now,
            publish_until=now + timedelta(hours=1),
        )
        notice.full_clean()


class ActiveNoticeServiceTests(TestCase):
    def test_draft_hidden(self):
        _make_notice(is_published=False, title_en='Draft')
        self.assertEqual(get_active_notices().count(), 0)
        self.assertEqual(
            compute_lifecycle_status(Notice.objects.get()),
            'draft',
        )

    def test_future_publish_at_hidden(self):
        now = timezone.now()
        notice = _make_notice(publish_at=now + timedelta(days=1))
        self.assertEqual(get_active_notices(at=now).count(), 0)
        self.assertEqual(compute_lifecycle_status(notice, at=now), 'scheduled')

    def test_past_publish_until_hidden(self):
        now = timezone.now()
        notice = _make_notice(publish_until=now - timedelta(minutes=1))
        self.assertEqual(get_active_notices(at=now).count(), 0)
        self.assertEqual(compute_lifecycle_status(notice, at=now), 'expired')

    def test_open_ended_published_visible(self):
        notice = _make_notice(publish_at=None, publish_until=None)
        qs = get_active_notices()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, notice.pk)
        self.assertEqual(compute_lifecycle_status(notice), 'active')

    def test_within_window_visible(self):
        now = timezone.now()
        _make_notice(
            publish_at=now - timedelta(hours=1),
            publish_until=now + timedelta(hours=1),
        )
        self.assertEqual(get_active_notices(at=now).count(), 1)

    def test_sort_order_respected(self):
        second = _make_notice(title_en='Second', sort_order=10)
        first = _make_notice(title_en='First', sort_order=1)
        ids = list(get_active_notices().values_list('pk', flat=True))
        self.assertEqual(ids, [first.pk, second.pk])


@override_settings(ROOT_URLCONF='core.urls')
class ActiveNoticeAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('notices:active-list')

    def test_anonymous_200_lists_active(self):
        _make_notice(
            title_en='Hello',
            title_bn='হ্যালো',
            body_en='World',
            body_bn='বিশ্ব',
            severity=Notice.Severity.WARNING,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row['title_en'], 'Hello')
        self.assertEqual(row['title_bn'], 'হ্যালো')
        self.assertEqual(row['body_en'], 'World')
        self.assertEqual(row['body_bn'], 'বিশ্ব')
        self.assertEqual(row['severity'], 'warning')
        self.assertIn('public_id', row)
        self.assertIn('sort_order', row)
        self.assertNotIn('is_published', row)

    def test_drafts_and_expired_omitted(self):
        now = timezone.now()
        _make_notice(title_en='Draft', is_published=False)
        _make_notice(
            title_en='Expired',
            publish_until=now - timedelta(seconds=1),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_pagination_caps_page_size(self):
        for i in range(3):
            _make_notice(title_en=f'N{i}', sort_order=i)
        response = self.client.get(self.url, {'page_size': 999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DRF caps at max_page_size=50; still returns all 3 rows.
        self.assertEqual(len(response.data['results']), 3)
        self.assertLessEqual(len(response.data['results']), 50)

    def test_draft_omitted_from_public_feed_after_admin_create(self):
        """Regression: drafts created via admin must stay off the public feed."""
        draft = _make_notice(title_en='Admin draft', is_published=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])
        self.assertFalse(
            any(row['public_id'] == str(draft.public_id) for row in response.data['results'])
        )


@override_settings(ROOT_URLCONF='core.urls')
class NoticeAdminAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='notice-admin',
            email='notice-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='notice-customer',
            email='notice-customer@example.com',
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

        self.list_url = reverse('notices:notices-list')
        self.active_url = reverse('notices:active-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _detail_url(self, public_id):
        return reverse('notices:notices-detail', kwargs={'public_id': public_id})

    def test_url_resolution_active_before_admin_detail(self):
        active_match = resolve('/notices/active/')
        self.assertEqual(active_match.func.cls, ActiveNoticeViewSet)

        notice = _make_notice(title_en='Route probe', is_published=False)
        detail_match = resolve(f'/notices/{notice.public_id}/')
        self.assertEqual(detail_match.func.cls, NoticeViewSet)

        list_match = resolve('/notices/')
        self.assertEqual(list_match.func.cls, NoticeViewSet)

    def test_anonymous_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        create = self.client.post(
            self.list_url,
            {'title_en': 'Nope', 'is_published': False},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_crud(self):
        self._auth_admin()
        create_resp = self.client.post(
            self.list_url,
            {
                'title_en': 'Holiday hours',
                'title_bn': 'ছুটির সময়সূচি',
                'body_en': 'Closed Friday.',
                'body_bn': 'শুক্রবার বন্ধ।',
                'severity': 'warning',
                'is_published': False,
                'sort_order': 2,
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        public_id = create_resp.data['public_id']
        self.assertEqual(create_resp.data['lifecycle_status'], 'draft')
        self.assertFalse(create_resp.data['is_published'])

        # Draft must not appear on public feed.
        public_feed = self.client.get(self.active_url)
        self.assertEqual(public_feed.status_code, status.HTTP_200_OK)
        self.assertEqual(public_feed.data['results'], [])

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data['count'], 1)

        detail_resp = self.client.get(self._detail_url(public_id))
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['title_en'], 'Holiday hours')
        self.assertIn('is_published', detail_resp.data)
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
        self.assertFalse(Notice.objects.filter(public_id=public_id).exists())

        list_after = self.client.get(self.list_url)
        self.assertEqual(list_after.data['count'], 0)

        public_gone = self.client.get(self.active_url)
        self.assertEqual(public_gone.data['results'], [])

    def test_validation_empty_titles_and_invalid_schedule(self):
        self._auth_admin()
        empty_titles = self.client.post(
            self.list_url,
            {
                'title_en': '',
                'title_bn': '',
                'body_en': 'x',
                'is_published': False,
            },
            format='json',
        )
        self.assertEqual(empty_titles.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title_en', empty_titles.data)
        self.assertIn('title_bn', empty_titles.data)
        self.assertEqual(Notice.objects.count(), 0)

        now = timezone.now()
        bad_window = self.client.post(
            self.list_url,
            {
                'title_en': 'Window',
                'publish_at': now.isoformat().replace('+00:00', 'Z'),
                'publish_until': now.isoformat().replace('+00:00', 'Z'),
                'is_published': False,
            },
            format='json',
        )
        self.assertEqual(bad_window.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('publish_until', bad_window.data)
        self.assertEqual(Notice.objects.count(), 0)

    def test_filters_and_lifecycle_status(self):
        self._auth_admin()
        now = timezone.now()
        draft = _make_notice(title_en='Draft A', is_published=False, severity='info')
        warning = _make_notice(
            title_en='Warn live',
            is_published=True,
            severity='warning',
        )
        expired = _make_notice(
            title_en='Expired B',
            is_published=True,
            severity='info',
            publish_until=now - timedelta(minutes=1),
        )

        published = self.client.get(self.list_url, {'is_published': 'true'})
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        published_ids = {row['public_id'] for row in published.data['results']}
        self.assertEqual(
            published_ids,
            {str(warning.public_id), str(expired.public_id)},
        )

        warnings = self.client.get(self.list_url, {'severity': 'warning'})
        self.assertEqual(warnings.status_code, status.HTTP_200_OK)
        self.assertEqual(len(warnings.data['results']), 1)
        self.assertEqual(warnings.data['results'][0]['public_id'], str(warning.public_id))

        search = self.client.get(self.list_url, {'search': 'Draft'})
        self.assertEqual(search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(search.data['results']), 1)
        self.assertEqual(search.data['results'][0]['public_id'], str(draft.public_id))

        draft_detail = self.client.get(self._detail_url(draft.public_id))
        self.assertEqual(draft_detail.data['lifecycle_status'], 'draft')

        expired_detail = self.client.get(self._detail_url(expired.public_id))
        self.assertEqual(expired_detail.data['lifecycle_status'], 'expired')

        warning_detail = self.client.get(self._detail_url(warning.public_id))
        self.assertEqual(warning_detail.data['lifecycle_status'], 'active')
