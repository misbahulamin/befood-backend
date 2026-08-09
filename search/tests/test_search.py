from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from search.models import PopularSearchPin, SearchDocument, SearchQueryEvent
from search.services.indexing import add_keyword, seed_common_keyword_packs, sync_search_catalog
from search.services.matching import MatchTier, score_document
from search.services.normalize import normalize_query
from search.services.ranking import rank_documents, suggest_documents
from user_management.models import AdminProfile, CustomerProfile


class NormalizeQueryTests(TestCase):
    def test_trim_case_and_spaces(self):
        self.assertEqual(normalize_query('  Kacchi  '), 'kacchi')

    def test_bangla_preserved(self):
        self.assertEqual(normalize_query('ভাত'), 'ভাত')

    def test_punctuation_stripped(self):
        self.assertEqual(normalize_query('kacchi!!!'), 'kacchi')
        self.assertEqual(normalize_query('chicken, rice'), 'chicken rice')


class MatchingRankingTests(TestCase):
    def setUp(self):
        seed_common_keyword_packs()
        self.kacchi = SearchDocument.objects.get(title_en='Kacchi Biryani')
        self.rice = SearchDocument.objects.get(title_en='Rice')
        self.chicken = SearchDocument.objects.create(
            document_type=SearchDocument.DocumentType.FOOD,
            title_en='Chicken Curry',
            title_bn='চিকেন কারি',
            is_active=True,
        )
        add_keyword(self.chicken, 'চিকেন', locale_hint='bn', raise_on_duplicate=False)
        add_keyword(self.chicken, 'chicken', locale_hint='en', raise_on_duplicate=False)
        self.biryani_pkg = SearchDocument.objects.create(
            document_type=SearchDocument.DocumentType.PACKAGE,
            title_en='Premium Biryani Package',
            is_active=True,
            popularity_score=10,
        )
        add_keyword(self.biryani_pkg, 'biryani', locale_hint='en', raise_on_duplicate=False)
        self.inactive = SearchDocument.objects.create(
            document_type=SearchDocument.DocumentType.FOOD,
            title_en='Hidden Kacchi',
            is_active=False,
        )
        add_keyword(self.inactive, 'kacchi', locale_hint='banglish', raise_on_duplicate=False)

    def test_exact_bangla_ranks_first(self):
        outcome = rank_documents('কাচ্চি')
        self.assertGreaterEqual(len(outcome.results), 1)
        self.assertEqual(outcome.results[0].document.id, self.kacchi.id)
        self.assertEqual(outcome.results[0].tier, MatchTier.EXACT)

    def test_partial_chicken_prefix(self):
        outcome = rank_documents('চিক')
        ids = {s.document.id for s in outcome.results}
        self.assertIn(self.chicken.id, ids)

    def test_synonyms_rice(self):
        for q in ('ভাত', 'vat', 'bhat', 'rice'):
            outcome = rank_documents(q)
            ids = [s.document.id for s in outcome.results]
            self.assertIn(self.rice.id, ids, msg=f'failed for {q}')

    def test_fuzzy_typo_kacchi(self):
        outcome = rank_documents('kachci')
        ids = [s.document.id for s in outcome.results] or [
            d.id for d in outcome.related
        ]
        self.assertIn(self.kacchi.id, ids)
        if not outcome.results:
            self.assertEqual(outcome.did_you_mean, self.kacchi.display_name)

    def test_fuzzy_chiken(self):
        scored = score_document(self.chicken, normalize_query('chiken'))
        self.assertIsNotNone(scored)
        self.assertEqual(scored.tier, MatchTier.FUZZY)

    def test_inactive_excluded(self):
        outcome = rank_documents('Hidden Kacchi')
        ids = {s.document.id for s in outcome.results}
        self.assertNotIn(self.inactive.id, ids)

    def test_suggestions_min_length(self):
        outcome = suggest_documents('k')
        self.assertEqual(outcome.results, [])
        outcome2 = suggest_documents('ka')
        self.assertGreaterEqual(len(outcome2.results), 1)


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.TokenAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.AllowAny',
        ],
        'DEFAULT_THROTTLE_RATES': {
            'anon': '1000/min',
            'user': '1000/min',
        },
    }
)
class SearchAPITests(APITestCase):
    def setUp(self):
        seed_common_keyword_packs()
        sync_search_catalog()
        self.search_url = '/api/v1/search/'
        self.suggest_url = '/api/v1/search/suggestions/'
        self.popular_url = '/api/v1/search/popular/'
        self.click_url = '/api/v1/search/events/click/'
        self.admin_docs_url = '/api/v1/web/search/documents/'
        self.admin_analytics_url = '/api/v1/web/search/analytics/'

        self.admin_user = User.objects.create_user(
            username='search-admin',
            email='search-admin@example.com',
            password='pass',
        )
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='search-customer',
            email='search-customer@example.com',
            password='pass',
        )
        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.customer_user.groups.add(customer_group)
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1711111111',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        PopularSearchPin.objects.create(
            term='Student Package',
            term_normalized='student package',
            sort_order=1,
            is_active=True,
        )

    def test_search_multi_type_and_analytics(self):
        response = self.client.get(self.search_url, {'q': 'chicken'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertTrue(
            SearchQueryEvent.objects.filter(query_normalized='chicken').exists()
        )
        for item in response.data['results']:
            self.assertIn('type', item)
            self.assertIn('public_id', item)
            self.assertIn('name', item)

    def test_search_requires_q(self):
        response = self.client.get(self.search_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suggestions_min_length(self):
        short = self.client.get(self.suggest_url, {'q': 'k'})
        self.assertEqual(short.status_code, status.HTTP_200_OK)
        self.assertEqual(short.data['results'], [])
        longer = self.client.get(self.suggest_url, {'q': 'ka'})
        self.assertEqual(longer.status_code, status.HTTP_200_OK)

    def test_popular_guest(self):
        response = self.client.get(self.popular_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        terms = [row['term'] for row in response.data['results']]
        self.assertIn('Student Package', terms)

    def test_click_event_validation(self):
        bad = self.client.post(
            self.click_url,
            {'public_id': '11111111-1111-1111-1111-111111111111'},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_404_NOT_FOUND)

        doc = SearchDocument.objects.filter(is_active=True).first()
        ok = self.client.post(
            self.click_url,
            {'public_id': str(doc.public_id), 'query': 'kacchi', 'position': 0},
            format='json',
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_admin_permission_and_crud_keywords(self):
        denied = self.client.get(self.admin_docs_url)
        self.assertIn(
            denied.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        denied_customer = self.client.get(self.admin_docs_url)
        self.assertEqual(denied_customer.status_code, status.HTTP_403_FORBIDDEN)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        create = self.client.post(
            self.admin_docs_url,
            {
                'document_type': 'food',
                'title_en': 'Beef Tehari',
                'title_bn': 'বিফ তেহারি',
                'keywords': [{'keyword_raw': 'tehari', 'locale_hint': 'banglish'}],
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        public_id = create.data['public_id']

        kw = self.client.post(
            f'{self.admin_docs_url}{public_id}/keywords/',
            {'keyword_raw': 'তেহারি', 'locale_hint': 'bn'},
            format='json',
        )
        self.assertEqual(kw.status_code, status.HTTP_201_CREATED)

        dup = self.client.post(
            f'{self.admin_docs_url}{public_id}/keywords/',
            {'keyword_raw': 'tehari', 'locale_hint': 'banglish'},
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        SearchQueryEvent.objects.create(
            query_original='tehari',
            query_normalized='tehari',
            result_count=0,
            is_zero_result=True,
        )
        analytics = self.client.get(self.admin_analytics_url)
        self.assertEqual(analytics.status_code, status.HTTP_200_OK)
        zero_queries = [row['query'] for row in analytics.data['zero_result_queries']]
        self.assertIn('tehari', zero_queries)

        bad_filter = self.client.get(self.admin_analytics_url, {'unknown': '1'})
        self.assertEqual(bad_filter.status_code, status.HTTP_400_BAD_REQUEST)
