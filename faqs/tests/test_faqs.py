from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import resolve
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_management.models import AdminProfile, CustomerProfile

from faqs.api.views import FaqQuestionViewSet, FaqTypeViewSet, PublicFaqCatalogViewSet
from faqs.models import FaqQuestion, FaqType
from faqs.services import get_public_faq_catalog

User = get_user_model()


def _make_type(**overrides) -> FaqType:
    defaults = {
        'name': 'How It Works',
        'sort_order': 0,
        'is_active': True,
    }
    defaults.update(overrides)
    faq_type = FaqType(**defaults)
    faq_type.full_clean()
    faq_type.save()
    return faq_type


def _make_question(faq_type: FaqType, **overrides) -> FaqQuestion:
    defaults = {
        'type': faq_type,
        'question': 'How do I order?',
        'answer': 'Choose a package and checkout.',
        'is_published': False,
        'sort_order': 0,
    }
    defaults.update(overrides)
    question = FaqQuestion(**defaults)
    question.full_clean()
    question.save()
    return question


class FaqAuthMixin:
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='faq-admin',
            email='faq-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.unverified_user = User.objects.create_user(
            username='faq-unverified',
            email='faq-unverified@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.unverified_user, is_verified=False)
        self.unverified_user.groups.add(self.admin_group)
        self.unverified_token = Token.objects.create(user=self.unverified_user)

        self.customer_user = User.objects.create_user(
            username='faq-customer',
            email='faq-customer@example.com',
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

        self.types_url = reverse('faqs:types-list')
        self.questions_url = reverse('faqs:questions-list')
        self.public_url = reverse('faqs:public-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_unverified(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.unverified_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _type_detail(self, public_id):
        return reverse('faqs:types-detail', kwargs={'public_id': public_id})

    def _question_detail(self, public_id):
        return reverse('faqs:questions-detail', kwargs={'public_id': public_id})


class FaqTypeAPITests(FaqAuthMixin, APITestCase):
    def test_url_resolution(self):
        self.assertEqual(resolve('/faqs/public/').func.cls, PublicFaqCatalogViewSet)
        self.assertEqual(resolve('/faqs/types/').func.cls, FaqTypeViewSet)
        self.assertEqual(resolve('/faqs/questions/').func.cls, FaqQuestionViewSet)

    def test_anonymous_denied(self):
        response = self.client.get(self.types_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.types_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_admin_denied(self):
        self._auth_unverified()
        response = self.client.get(self.types_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verified_admin_crud(self):
        self._auth_admin()
        create = self.client.post(
            self.types_url,
            {'name': 'Pricing & Flexibility', 'sort_order': 1},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        public_id = create.data['public_id']
        self.assertNotIn('id', create.data)
        self.assertEqual(create.data['name'], 'Pricing & Flexibility')
        self.assertTrue(create.data['is_active'])

        listing = self.client.get(self.types_url)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data['count'], 1)

        detail = self.client.get(self._type_detail(public_id))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['public_id'], public_id)

        patch = self.client.patch(
            self._type_detail(public_id),
            {'sort_order': 5, 'is_active': False},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['sort_order'], 5)
        self.assertFalse(patch.data['is_active'])

        delete = self.client.delete(self._type_detail(public_id))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(FaqType.objects.filter(public_id=public_id).exists())

    def test_duplicate_name_rejected(self):
        _make_type(name='Freshness & Delivery')
        self._auth_admin()
        response = self.client.post(
            self.types_url,
            {'name': 'freshness & delivery'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_delete_blocked_when_questions_exist(self):
        faq_type = _make_type(name='Dietary & Nutrition')
        _make_question(faq_type, question='Is it halal?')
        self._auth_admin()
        response = self.client.delete(self._type_detail(faq_type.public_id))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(FaqType.objects.filter(pk=faq_type.pk).exists())

    def test_integer_pk_path_not_resolved(self):
        faq_type = _make_type(name='Chefs & Quality')
        self._auth_admin()
        response = self.client.get(f'/faqs/types/{faq_type.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FaqQuestionAPITests(FaqAuthMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.faq_type = _make_type(name='Portions & Family')

    def test_anonymous_denied(self):
        response = self.client.get(self.questions_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.post(
            self.questions_url,
            {
                'type_public_id': str(self.faq_type.public_id),
                'question': 'Q',
                'answer': 'A',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_defaults_unpublished(self):
        self._auth_admin()
        response = self.client.post(
            self.questions_url,
            {
                'type_public_id': str(self.faq_type.public_id),
                'question': 'How large are portions?',
                'answer': 'Family size by default.',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_published'])
        self.assertEqual(response.data['type_public_id'], str(self.faq_type.public_id))
        self.assertNotIn('id', response.data)

    def test_publish_and_unpublish(self):
        question = _make_question(self.faq_type, is_published=False)
        self._auth_admin()
        published = self.client.patch(
            self._question_detail(question.public_id),
            {'is_published': True},
            format='json',
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertTrue(published.data['is_published'])

        unpublished = self.client.patch(
            self._question_detail(question.public_id),
            {'is_published': False},
            format='json',
        )
        self.assertEqual(unpublished.status_code, status.HTTP_200_OK)
        self.assertFalse(unpublished.data['is_published'])

    def test_filter_by_type_and_published(self):
        other = _make_type(name='Other Type', sort_order=2)
        _make_question(self.faq_type, question='Published Q', is_published=True)
        _make_question(self.faq_type, question='Draft Q', is_published=False)
        _make_question(other, question='Other Q', is_published=True)

        self._auth_admin()
        by_type = self.client.get(
            self.questions_url,
            {'type_public_id': str(self.faq_type.public_id)},
        )
        self.assertEqual(by_type.status_code, status.HTTP_200_OK)
        self.assertEqual(by_type.data['count'], 2)

        published = self.client.get(self.questions_url, {'is_published': 'true'})
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertEqual(published.data['count'], 2)

    def test_invalid_type_public_id_rejected(self):
        self._auth_admin()
        response = self.client.post(
            self.questions_url,
            {
                'type_public_id': '00000000-0000-0000-0000-000000000099',
                'question': 'Orphan?',
                'answer': 'No.',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('type_public_id', response.data)

    def test_delete_question(self):
        question = _make_question(self.faq_type)
        self._auth_admin()
        response = self.client.delete(self._question_detail(question.public_id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(FaqQuestion.objects.filter(pk=question.pk).exists())


class PublicFaqFeedTests(FaqAuthMixin, APITestCase):
    def test_public_feed_no_auth(self):
        faq_type = _make_type(name='How It Works', sort_order=1)
        _make_question(
            faq_type,
            question='How does delivery work?',
            answer='We deliver daily.',
            is_published=True,
            sort_order=0,
        )
        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'How It Works')
        self.assertEqual(len(response.data[0]['questions']), 1)
        self.assertNotIn('id', response.data[0])
        self.assertNotIn('id', response.data[0]['questions'][0])
        self.assertNotIn('is_published', response.data[0]['questions'][0])

    def test_excludes_unpublished_and_empty_and_inactive(self):
        active = _make_type(name='Active With Mix', sort_order=0)
        _make_question(active, question='Visible', answer='Yes', is_published=True)
        _make_question(active, question='Hidden', answer='No', is_published=False)

        empty = _make_type(name='Empty Type', sort_order=1)
        _make_question(empty, question='Draft only', answer='Soon', is_published=False)

        inactive = _make_type(name='Inactive Type', sort_order=2, is_active=False)
        _make_question(
            inactive,
            question='Should not show',
            answer='Nope',
            is_published=True,
        )

        response = self.client.get(self.public_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data]
        self.assertEqual(names, ['Active With Mix'])
        questions = response.data[0]['questions']
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['question'], 'Visible')

    def test_ordering(self):
        second = _make_type(name='Second', sort_order=2)
        first = _make_type(name='First', sort_order=1)
        _make_question(
            second,
            question='S2',
            answer='A',
            is_published=True,
            sort_order=2,
        )
        _make_question(
            second,
            question='S1',
            answer='A',
            is_published=True,
            sort_order=1,
        )
        _make_question(
            first,
            question='F1',
            answer='A',
            is_published=True,
            sort_order=0,
        )

        catalog = list(get_public_faq_catalog())
        self.assertEqual([t.name for t in catalog], ['First', 'Second'])
        self.assertEqual(
            [q.question for q in catalog[1].questions.all()],
            ['S1', 'S2'],
        )

        response = self.client.get(self.public_url)
        self.assertEqual(
            [row['name'] for row in response.data],
            ['First', 'Second'],
        )
        self.assertEqual(
            [q['question'] for q in response.data[1]['questions']],
            ['S1', 'S2'],
        )
