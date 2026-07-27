from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile

from blogs.api.views import (
    BlogArticleViewSet,
    BlogCategoryViewSet,
    PublicBlogArticleViewSet,
)
from blogs.models import BlogArticle, BlogCategory
from blogs.services import get_popular_articles, get_related_articles

User = get_user_model()


def make_test_image(name='cover.jpg', size=(100, 100), color='green'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _make_category(**overrides) -> BlogCategory:
    defaults = {
        'name': 'Nutrition',
        'slug': 'nutrition',
        'sort_order': 0,
        'is_active': True,
    }
    defaults.update(overrides)
    category = BlogCategory(**defaults)
    category.full_clean()
    category.save()
    return category


def _make_article(author, **overrides) -> BlogArticle:
    defaults = {
        'author': author,
        'title': 'Healthy Meal Prep',
        'slug': 'healthy-meal-prep',
        'excerpt': 'A short summary',
        'content': 'Full article body goes here.',
        'is_published': False,
        'view_count': 0,
    }
    defaults.update(overrides)
    article = BlogArticle(**defaults)
    # Skip full_clean when publishing without cover in helpers that set fields
    # intentionally for draft fixtures; callers publishing must attach cover first.
    if not article.is_published:
        article.full_clean()
    article.save()
    return article


class BlogAuthMixin:
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='blog-admin',
            email='blog-admin@example.com',
            password='StrongPassword123',
            first_name='Blog',
            last_name='Admin',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.unverified_user = User.objects.create_user(
            username='blog-unverified',
            email='blog-unverified@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.unverified_user, is_verified=False)
        self.unverified_user.groups.add(self.admin_group)
        self.unverified_token = Token.objects.create(user=self.unverified_user)

        self.customer_user = User.objects.create_user(
            username='blog-customer',
            email='blog-customer@example.com',
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

        self.categories_url = reverse('blogs:categories-list')
        self.articles_url = reverse('blogs:articles-list')
        self.public_url = reverse('blogs:public-list')
        self.popular_url = reverse('blogs:public-popular')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_unverified(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.unverified_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _category_detail(self, public_id):
        return reverse('blogs:categories-detail', kwargs={'public_id': public_id})

    def _article_detail(self, public_id):
        return reverse('blogs:articles-detail', kwargs={'public_id': public_id})

    def _public_detail(self, public_id):
        return reverse('blogs:public-detail', kwargs={'public_id': public_id})

    def _related_url(self, public_id):
        return reverse('blogs:public-related', kwargs={'public_id': public_id})


class BlogCategoryAPITests(BlogAuthMixin, APITestCase):
    def test_url_resolution(self):
        self.assertEqual(resolve('/blogs/public/').func.cls, PublicBlogArticleViewSet)
        self.assertEqual(resolve('/blogs/public/popular/').func.cls, PublicBlogArticleViewSet)
        self.assertEqual(resolve('/blogs/categories/').func.cls, BlogCategoryViewSet)
        self.assertEqual(resolve('/blogs/articles/').func.cls, BlogArticleViewSet)

    def test_anonymous_denied(self):
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_admin_denied(self):
        self._auth_unverified()
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verified_admin_crud(self):
        self._auth_admin()
        create = self.client.post(
            self.categories_url,
            {'name': 'Meal Plans', 'sort_order': 1},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        public_id = create.data['public_id']
        self.assertNotIn('id', create.data)
        self.assertEqual(create.data['name'], 'Meal Plans')
        self.assertEqual(create.data['slug'], 'meal-plans')
        self.assertTrue(create.data['is_active'])

        listing = self.client.get(self.categories_url)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data['count'], 1)

        detail = self.client.get(self._category_detail(public_id))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        patch = self.client.patch(
            self._category_detail(public_id),
            {'sort_order': 5, 'is_active': False},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['sort_order'], 5)
        self.assertFalse(patch.data['is_active'])

        delete = self.client.delete(self._category_detail(public_id))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BlogCategory.objects.filter(public_id=public_id).exists())

    def test_duplicate_name_rejected(self):
        _make_category(name='Recipes', slug='recipes')
        self._auth_admin()
        response = self.client.post(
            self.categories_url,
            {'name': 'recipes'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_delete_nullifies_article_category(self):
        category = _make_category(name='Lifestyle', slug='lifestyle')
        article = _make_article(
            self.admin_user,
            category=category,
            title='Linked Article',
            slug='linked-article',
        )
        self._auth_admin()
        response = self.client.delete(self._category_detail(category.public_id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        article.refresh_from_db()
        self.assertIsNone(article.category)


class BlogArticleAPITests(BlogAuthMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.category = _make_category(name='Tips', slug='tips')

    def test_anonymous_denied(self):
        response = self.client.get(self.articles_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.articles_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_admin_denied(self):
        self._auth_unverified()
        response = self.client.post(
            self.articles_url,
            {'title': 'Nope', 'content': 'Denied'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_draft_sets_author_automatically(self):
        self._auth_admin()
        response = self.client.post(
            self.articles_url,
            {
                'title': 'Draft Guide',
                'content': 'Draft body',
                'category_public_id': str(self.category.public_id),
                'author': 99999,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_published'])
        self.assertEqual(response.data['view_count'], 0)
        self.assertIsNone(response.data['published_at'])
        self.assertEqual(response.data['author_display_name'], 'Blog Admin')
        self.assertNotIn('id', response.data)
        article = BlogArticle.objects.get(public_id=response.data['public_id'])
        self.assertEqual(article.author_id, self.admin_user.id)

    def test_publish_sets_published_at_and_requires_cover(self):
        article = _make_article(
            self.admin_user,
            title='Needs Cover',
            slug='needs-cover',
            category=self.category,
        )
        self._auth_admin()
        without_cover = self.client.patch(
            self._article_detail(article.public_id),
            {'is_published': True},
            format='json',
        )
        self.assertEqual(without_cover.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cover_image', without_cover.data)
        article.refresh_from_db()
        self.assertFalse(article.is_published)
        self.assertIsNone(article.published_at)

        with_cover = self.client.patch(
            self._article_detail(article.public_id),
            {
                'is_published': True,
                'cover_image': make_test_image(),
                'cover_image_title': 'Meal box',
            },
            format='multipart',
        )
        self.assertEqual(with_cover.status_code, status.HTTP_200_OK)
        self.assertTrue(with_cover.data['is_published'])
        self.assertIsNotNone(with_cover.data['published_at'])
        published_at = with_cover.data['published_at']

        unpublish = self.client.patch(
            self._article_detail(article.public_id),
            {'is_published': False},
            format='json',
        )
        self.assertEqual(unpublish.status_code, status.HTTP_200_OK)
        self.assertFalse(unpublish.data['is_published'])
        self.assertEqual(unpublish.data['published_at'], published_at)

    def test_invalid_category_public_id_rejected(self):
        self._auth_admin()
        response = self.client.post(
            self.articles_url,
            {
                'title': 'Bad Category',
                'content': 'Body',
                'category_public_id': '00000000-0000-0000-0000-000000000099',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('category_public_id', response.data)

    def test_filter_by_is_published(self):
        draft = _make_article(
            self.admin_user,
            title='Draft Filter',
            slug='draft-filter',
            is_published=False,
        )
        published = _make_article(
            self.admin_user,
            title='Published Filter',
            slug='published-filter',
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('published.jpg'),
        )
        self._auth_admin()
        response = self.client.get(self.articles_url, {'is_published': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['public_id'] for row in response.data['results']}
        self.assertIn(str(published.public_id), ids)
        self.assertNotIn(str(draft.public_id), ids)


class PublicBlogFeedAPITests(BlogAuthMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.category = _make_category(name='Public Cat', slug='public-cat')
        self.draft = _make_article(
            self.admin_user,
            title='Secret Draft',
            slug='secret-draft',
            content='Draft content secret',
            is_published=False,
        )
        self.published = _make_article(
            self.admin_user,
            title='Public Post',
            slug='public-post',
            excerpt='Card summary',
            content='Full public content',
            category=self.category,
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('public.jpg'),
            cover_image_title='Cover',
            view_count=3,
        )

    def test_public_list_no_auth_excludes_drafts_omits_content(self):
        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['public_id'], str(self.published.public_id))
        self.assertNotIn('content', row)
        self.assertNotIn('id', row)
        self.assertEqual(row['author_display_name'], 'Blog Admin')
        self.assertEqual(row['category']['public_id'], str(self.category.public_id))

    def test_detail_returns_content_and_increments_views(self):
        before = self.published.view_count
        response = self.client.get(self._public_detail(self.published.public_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content'], 'Full public content')
        self.assertNotIn('id', response.data)
        self.published.refresh_from_db()
        self.assertEqual(self.published.view_count, before + 1)

    def test_unpublished_and_missing_detail_404(self):
        unpublished = self.client.get(self._public_detail(self.draft.public_id))
        self.assertEqual(unpublished.status_code, status.HTTP_404_NOT_FOUND)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.view_count, 0)

        missing = self.client.get(
            self._public_detail('00000000-0000-0000-0000-000000000001')
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)


class PopularBlogAPITests(BlogAuthMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.low = _make_article(
            self.admin_user,
            title='Low Views',
            slug='low-views',
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('low.jpg'),
            view_count=1,
        )
        self.high = _make_article(
            self.admin_user,
            title='High Views',
            slug='high-views',
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('high.jpg'),
            view_count=50,
        )
        self.draft_high = _make_article(
            self.admin_user,
            title='Draft High',
            slug='draft-high',
            is_published=False,
            view_count=999,
        )

    def test_popular_ordered_excludes_drafts(self):
        response = self.client.get(self.popular_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['public_id'], str(self.high.public_id))
        self.assertEqual(response.data[1]['public_id'], str(self.low.public_id))
        self.assertNotIn('content', response.data[0])
        ids = {row['public_id'] for row in response.data}
        self.assertNotIn(str(self.draft_high.public_id), ids)

    def test_limit_clamping(self):
        response = self.client.get(self.popular_url, {'limit': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        clamped = list(get_popular_articles(limit=100))
        self.assertLessEqual(len(clamped), 20)


class RelatedBlogAPITests(BlogAuthMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.cat_a = _make_category(name='Cat A', slug='cat-a')
        self.cat_b = _make_category(name='Cat B', slug='cat-b')
        self.source = _make_article(
            self.admin_user,
            title='Source',
            slug='source',
            category=self.cat_a,
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('source.jpg'),
            view_count=10,
        )
        self.same_cat = _make_article(
            self.admin_user,
            title='Same Cat',
            slug='same-cat',
            category=self.cat_a,
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('same.jpg'),
            view_count=8,
        )
        self.other_cat = _make_article(
            self.admin_user,
            title='Other Cat',
            slug='other-cat',
            category=self.cat_b,
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('other.jpg'),
            view_count=20,
        )
        self.draft = _make_article(
            self.admin_user,
            title='Draft Related',
            slug='draft-related',
            category=self.cat_a,
            is_published=False,
        )

    def test_related_excludes_self_prefers_same_category(self):
        response = self.client.get(self._related_url(self.source.public_id), {'limit': 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row['public_id'] for row in response.data]
        self.assertNotIn(str(self.source.public_id), ids)
        self.assertEqual(ids[0], str(self.same_cat.public_id))
        self.assertIn(str(self.other_cat.public_id), ids)
        self.assertNotIn('content', response.data[0])

    def test_backfill_and_no_category_path(self):
        related = get_related_articles(self.source, limit=2)
        self.assertEqual(len(related), 2)
        self.assertEqual(related[0].pk, self.same_cat.pk)
        self.assertEqual(related[1].pk, self.other_cat.pk)

        uncategorized = _make_article(
            self.admin_user,
            title='No Cat Source',
            slug='no-cat-source',
            category=None,
            is_published=True,
            published_at=timezone.now(),
            cover_image=make_test_image('nocat.jpg'),
        )
        related_global = get_related_articles(uncategorized, limit=3)
        self.assertTrue(all(row.pk != uncategorized.pk for row in related_global))
        self.assertGreaterEqual(len(related_global), 1)

    def test_related_404_for_unpublished_source(self):
        response = self.client.get(self._related_url(self.draft.public_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
