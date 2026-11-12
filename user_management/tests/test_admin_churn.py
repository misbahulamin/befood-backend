"""Admin churn list, analytics, follow-ups, and dashboard KPIs."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import CustomerSubscription, SubscriptionCancellation
from user_management.models import AdminProfile, CustomerProfile
from user_management.services.admin_dashboard import build_dashboard_summary
from wallet.services.ledger import credit_wallet, get_or_create_wallet


DHAKA = ZoneInfo('Asia/Dhaka')
TODAY = date(2026, 8, 15)


def make_test_image(name='meal.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (40, 40), 'green').save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class AdminChurnAPITests(APITestCase):
    def setUp(self):
        self._today = patch(
            'orders.services.customer_lifecycle.business_today',
            return_value=TODAY,
        )
        self._today.start()
        self.addCleanup(self._today.stop)
        self._dash_today = patch(
            'orders.services.meal_off.meal_off_business_now',
            return_value=datetime(2026, 8, 15, 12, 0, tzinfo=DHAKA),
        )
        self._dash_today.start()
        self.addCleanup(self._dash_today.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.meal = MealCategory.objects.create(
            meal_name='Churn Plan',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('churn.jpg'),
            is_active=True,
            is_subscribable=True,
        )

        self.admin_user = User.objects.create_user(
            username='churn_admin',
            email='churn_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='churn_customer',
            email='churn_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712888001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        credit_wallet(get_or_create_wallet(self.customer), Decimal('500.00'))

        self.sub = CustomerSubscription.objects.create(
            customer=self.customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_period_snapshot='both',
            quantity=1,
            status=CustomerSubscription.Status.CANCELLED,
            started_on=TODAY - timedelta(days=40),
            cancel_effective_on=TODAY - timedelta(days=5),
            cancelled_at=datetime(2026, 8, 10, 12, 0, tzinfo=DHAKA),
            cancel_source=CustomerSubscription.CancelSource.CUSTOMER,
        )
        SubscriptionCancellation.objects.create(
            subscription=self.sub,
            customer=self.customer,
            reason_code='price_too_high',
            reason_text='',
            cancelled_by='customer',
        )

        self.never_user = User.objects.create_user(
            username='never_churn',
            email='never_churn@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.never_user.groups.add(customer_group)
        CustomerProfile.objects.create(
            user=self.never_user,
            phone='1712888002',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

        self.list_url = reverse('web_churn:customers')
        self.analytics_url = reverse('web_churn:analytics')
        self.follow_ups_url = reverse('web_churn:follow-ups')
        self.customers_url = reverse('web_customers:admin-customer-list')
        self.dashboard_url = reverse('web_admin_dashboard:summary')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def test_churn_customers_default_unsubscribed(self):
        self._auth_admin()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['public_id'] for row in response.data['results']}
        self.assertIn(str(self.customer.public_id), ids)
        row = next(
            r for r in response.data['results'] if r['public_id'] == str(self.customer.public_id)
        )
        self.assertEqual(row['lifecycle'], 'unsubscribed')
        self.assertEqual(row['last_cancel_reason'], 'price_too_high')
        self.assertIsNotNone(row['churn_date'])

    def test_churn_customers_csv(self):
        self._auth_admin()
        response = self.client.get(self.list_url, {'format': 'csv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('price_too_high', response.content.decode())

    def test_churn_customers_requires_admin(self):
        response = self.client.get(self.list_url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_customer_list_lifecycle_filter(self):
        self._auth_admin()
        response = self.client.get(self.customers_url, {'lifecycle': 'unsubscribed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['public_id'] for row in response.data['results']}
        self.assertIn(str(self.customer.public_id), ids)
        self.assertTrue(all(r.get('lifecycle') == 'unsubscribed' for r in response.data['results']))

    def test_customer_list_unknown_filter_400(self):
        self._auth_admin()
        response = self.client.get(self.customers_url, {'not_a_filter': '1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_analytics_period(self):
        self._auth_admin()
        response = self.client.get(
            self.analytics_url,
            {'from': '2026-08-01', 'to': '2026-08-31'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('kpis', response.data)
        self.assertIn('breakdowns', response.data)
        self.assertIn('time_series', response.data)
        self.assertIn('cohorts', response.data)
        self.assertIn('leading_signals', response.data)
        self.assertGreaterEqual(response.data['kpis']['churned_count'], 1)

    def test_analytics_missing_range_400(self):
        self._auth_admin()
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_follow_up_crud(self):
        self._auth_admin()
        create = self.client.post(
            self.follow_ups_url,
            {
                'customer_public_id': str(self.customer.public_id),
                'status': 'contacted',
                'note': 'Called customer',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        public_id = create.data['public_id']
        detail_url = reverse(
            'web_churn:follow-up-detail',
            kwargs={'public_id': public_id},
        )
        patch = self.client.patch(
            detail_url,
            {'status': 'won_back'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['status'], 'won_back')

    def test_dashboard_churn_fields(self):
        summary = build_dashboard_summary()
        for key in (
            'unsubscribed_this_month',
            'churn_rate_this_month',
            'at_risk_count',
            'won_back_this_month',
            'total_customers',
            'active_subscribers',
        ):
            self.assertIn(key, summary)
