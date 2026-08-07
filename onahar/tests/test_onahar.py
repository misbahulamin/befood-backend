from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from onahar.models import (
    OnaharContribution,
    OnaharDistribution,
    OnaharMonthlyProgress,
    OnaharPointEvent,
    OnaharPrivacyPreference,
)
from onahar.services.contribution import (
    close_month,
    credit_for_delivery,
    reverse_for_delivery,
    update_contribution_target,
)
from onahar.services.distribution import (
    OnaharDistributionError,
    cancel_distribution,
    create_distribution,
    publish_distribution,
)
from onahar.services.fund import fund_summary, get_or_create_settings
from onahar.services.privacy import customer_display_name, get_or_create_privacy
from orders.models import Order, OrderDelivery
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='proof.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (80, 80), 'blue').save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(ONAHAR_ENABLED=True)
class OnaharEngineTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='onahar_cust',
            email='onahar_cust@example.com',
            password='x',
            first_name='Rahim',
            last_name='Ahmed',
        )
        self.user.groups.add(group)
        self.customer = CustomerProfile.objects.create(
            user=self.user,
            phone='1710000101',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.meal = MealCategory.objects.create(
            meal_name='Onahar Test Package',
            meal_type=MealCategory.MealType.MONTHLY,
            total_price=Decimal('1500.00'),
            meal_thumbnail=make_test_image('pkg.jpg'),
        )
        today = date.today()
        self.order = Order.objects.create(
            customer=self.customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_type_snapshot=self.meal.meal_type,
            meal_period_snapshot='lunch',
            total_price_snapshot=Decimal('1500.00'),
            per_meal_price_snapshot=Decimal('50.00'),
            order_status=Order.OrderStatus.ACTIVE,
            order_start_date=today.replace(day=1),
            order_end_date=today,
            service_days_count=1,
            order_month=today.strftime('%Y-%m'),
        )
        settings = get_or_create_settings()
        settings.contribution_target = 5
        settings.save(update_fields=['contribution_target', 'updated_at'])

    def _delivery(self, day_offset=0):
        d = date.today() + timedelta(days=day_offset)
        return OrderDelivery.objects.create(
            order=self.order,
            service_date=d,
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
        )

    def test_credit_idempotent(self):
        delivery = self._delivery()
        e1 = credit_for_delivery(delivery)
        e2 = credit_for_delivery(delivery)
        self.assertEqual(e1.pk, e2.pk)
        self.assertEqual(
            OnaharPointEvent.objects.filter(
                order_delivery=delivery,
                event_type=OnaharPointEvent.EventType.CREDIT,
            ).count(),
            1,
        )
        progress = OnaharMonthlyProgress.objects.get(customer=self.customer)
        self.assertEqual(progress.net_points, 1)

    def test_multi_contribution_and_fund(self):
        for i in range(12):
            credit_for_delivery(self._delivery(day_offset=i))
        progress = OnaharMonthlyProgress.objects.get(customer=self.customer)
        self.assertEqual(progress.target_snapshot, 5)
        self.assertEqual(progress.net_points, 12)
        self.assertEqual(progress.contributions_earned, 2)
        self.assertEqual(progress.remaining_points, 2)
        summary = fund_summary()
        self.assertEqual(summary['total_contributed_meals'], 2)
        self.assertEqual(summary['available_meals'], 2)
        self.assertEqual(
            OnaharContribution.objects.filter(kind=OnaharContribution.Kind.EARNED).count(),
            2,
        )

    def test_month_close_expires_remainder_idempotent(self):
        for i in range(7):
            credit_for_delivery(self._delivery(day_offset=i))
        progress = OnaharMonthlyProgress.objects.get(customer=self.customer)
        ym = progress.year_month
        r1 = close_month(ym)
        self.assertEqual(r1['closed'], 1)
        progress.refresh_from_db()
        self.assertEqual(progress.status, OnaharMonthlyProgress.Status.CLOSED)
        self.assertEqual(progress.contributions_earned, 1)
        self.assertEqual(progress.expired_points, 2)
        r2 = close_month(ym)
        self.assertEqual(r2['skipped'], 1)
        self.assertEqual(fund_summary()['total_contributed_meals'], 1)

    def test_target_snapshot_stable(self):
        credit_for_delivery(self._delivery())
        progress = OnaharMonthlyProgress.objects.get(customer=self.customer)
        self.assertEqual(progress.target_snapshot, 5)
        update_contribution_target(10)
        progress.refresh_from_db()
        self.assertEqual(progress.target_snapshot, 5)
        self.assertEqual(get_or_create_settings().contribution_target, 10)

    def test_reverse_adjusts_contribution(self):
        deliveries = [self._delivery(day_offset=i) for i in range(5)]
        for d in deliveries:
            credit_for_delivery(d)
        self.assertEqual(fund_summary()['available_meals'], 1)
        reverse_for_delivery(deliveries[-1])
        progress = OnaharMonthlyProgress.objects.get(customer=self.customer)
        self.assertEqual(progress.net_points, 4)
        self.assertEqual(progress.contributions_earned, 0)
        self.assertEqual(fund_summary()['available_meals'], 0)
        self.assertTrue(
            OnaharContribution.objects.filter(kind=OnaharContribution.Kind.ADJUSTMENT).exists()
        )

    def test_publish_rejects_over_fund(self):
        credit_for_delivery(self._delivery())
        # Need 5 points for 1 contribution with target 5
        for i in range(1, 5):
            credit_for_delivery(self._delivery(day_offset=i))
        self.assertEqual(fund_summary()['available_meals'], 1)
        admin = User.objects.create_user(username='oa', password='x')
        dist = create_distribution(
            data={
                'title': 'Test Dist',
                'location': 'Dhaka',
                'distribution_date': date.today(),
                'meals_distributed': 5,
                'full_address': '',
                'description': '',
                'beneficiary_info': '',
            },
            actor=admin,
        )
        with self.assertRaises(OnaharDistributionError):
            publish_distribution(dist, actor=admin)

    def test_publish_and_cancel_restore(self):
        for i in range(5):
            credit_for_delivery(self._delivery(day_offset=i))
        admin = User.objects.create_user(username='oa2', password='x')
        dist = create_distribution(
            data={
                'title': 'Station Feed',
                'location': 'Kamalapur',
                'distribution_date': date.today(),
                'meals_distributed': 1,
                'full_address': 'Dhaka',
                'description': 'Test',
                'beneficiary_info': '',
            },
            actor=admin,
        )
        publish_distribution(dist, actor=admin)
        self.assertEqual(fund_summary()['available_meals'], 0)
        cancel_distribution(dist, actor=admin)
        self.assertEqual(fund_summary()['available_meals'], 1)
        dist.refresh_from_db()
        self.assertEqual(dist.status, OnaharDistribution.Status.CANCELLED)

    def test_privacy_masking(self):
        pref = get_or_create_privacy(self.customer)
        pref.display_mode = OnaharPrivacyPreference.DisplayMode.PARTIAL
        pref.save()
        self.assertIn('***', customer_display_name(self.customer, pref))
        pref.display_mode = OnaharPrivacyPreference.DisplayMode.ANONYMOUS
        pref.save()
        self.assertEqual(customer_display_name(self.customer, pref), 'Anonymous Contributor')


@override_settings(ONAHAR_ENABLED=True, MEDIA_ROOT='test_media')
class OnaharAPITests(APITestCase):
    def setUp(self):
        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.customer_user = User.objects.create_user(
            username='onahar_api_c',
            email='onahar_api_c@example.com',
            password='StrongPassword123',
            first_name='Karim',
            last_name='Hasan',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1710000202',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.admin_user = User.objects.create_user(
            username='onahar_api_a',
            email='onahar_api_a@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        get_or_create_settings()

    def test_public_stats_unauthenticated(self):
        url = reverse('onahar:stats')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('total_meals_contributed', res.data)
        self.assertIn('current_contribution_target', res.data)

    def test_customer_me_requires_auth(self):
        url = reverse('onahar:me')
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('current_points', res.data)
        self.assertIn('target', res.data)

    def test_privacy_patch(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        url = reverse('onahar:me-privacy')
        res = self.client.patch(url, {'display_mode': 'anonymous'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['display_mode'], 'anonymous')
        bad = self.client.patch(url, {'display_mode': 'secret'}, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_settings_authz(self):
        url = reverse('web_onahar:settings')
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        patch = self.client.patch(url, {'contribution_target': 45}, format='json')
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['contribution_target'], 45)

    def test_admin_distribution_flow(self):
        # Seed fund via contributions
        meal = MealCategory.objects.create(
            meal_name='API Pkg',
            meal_type=MealCategory.MealType.DAILY,
            total_price=Decimal('100.00'),
            meal_thumbnail=make_test_image('api.jpg'),
        )
        today = date.today()
        order = Order.objects.create(
            customer=self.customer,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_type_snapshot=meal.meal_type,
            meal_period_snapshot='lunch',
            total_price_snapshot=Decimal('100.00'),
            per_meal_price_snapshot=Decimal('50.00'),
            order_status=Order.OrderStatus.ACTIVE,
            order_start_date=today,
            order_end_date=today,
            service_days_count=1,
            order_month=today.strftime('%Y-%m'),
        )
        settings = get_or_create_settings()
        settings.contribution_target = 2
        settings.save(update_fields=['contribution_target'])
        for i in range(2):
            d = OrderDelivery.objects.create(
                order=order,
                service_date=today,
                meal_period=OrderDelivery.MealPeriod.LUNCH if i == 0 else OrderDelivery.MealPeriod.DINNER,
                status=OrderDelivery.DeliveryStatus.DELIVERED,
            )
            credit_for_delivery(d)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        create_url = reverse('web_onahar:distributions')
        created = self.client.post(
            create_url,
            {
                'title': 'Rail Station',
                'location': 'Kamalapur',
                'full_address': 'Dhaka',
                'distribution_date': today.isoformat(),
                'meals_distributed': 1,
                'description': 'Feed',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        public_id = created.data['public_id']
        publish = self.client.post(reverse('web_onahar:distribution-publish', kwargs={'public_id': public_id}))
        self.assertEqual(publish.status_code, status.HTTP_200_OK)
        self.assertEqual(publish.data['status'], 'published')

        public_list = self.client.get(reverse('onahar:distributions'))
        # clear auth for public
        self.client.credentials()
        public_list = self.client.get(reverse('onahar:distributions'))
        self.assertEqual(public_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(public_list.data['count'], 1)
