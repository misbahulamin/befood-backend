from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import CustomerSubscription, Order, OrderDelivery
from orders.services.customer_lifecycle import month_bounds_dhaka
from orders.services.meal_off import CUTOFF_PASSED_NOTE
from user_management.models import AdminProfile, CustomerProfile
from user_management.services.admin_customer_analytics import (
    BLOCKED_ESTIMATE_NOTE,
    build_blocked_low_balance_section,
    build_consumption_section,
    build_customer_analytics,
    build_matrix_section,
    build_meal_off_section,
    build_wallet_recharge_section,
    parse_analytics_window,
)
from wallet.models import Wallet, WalletTransaction

DHAKA = ZoneInfo('Asia/Dhaka')


def make_test_image(name='meal.jpg', size=(40, 40), color='blue'):
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AdminCustomerAnalyticsServiceTests(TestCase):
    def setUp(self):
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.meal = MealCategory.objects.create(
            meal_name='Regular Package',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('analytics-meal.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        self.customer = self._make_customer('analytics-cust')
        self.wallet = Wallet.objects.create(
            customer=self.customer,
            balance=Decimal('500.00'),
            recharge_balance=Decimal('500.00'),
        )
        self.subscription = CustomerSubscription.objects.create(
            customer=self.customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_period_snapshot=self.meal.meal_period,
            quantity=1,
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 1, 1),
        )

    def _make_customer(self, username: str) -> CustomerProfile:
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='StrongPassword123',
            first_name='Ana',
            last_name='Lytics',
            is_active=True,
        )
        user.groups.add(self.customer_group)
        return CustomerProfile.objects.create(
            user=user,
            phone=f'17{abs(hash(username)) % 10_000_000:08d}',
            is_email_verified=True,
            is_phone_verified=True,
        )

    def _delivery(self, **kwargs) -> OrderDelivery:
        defaults = {
            'subscription': self.subscription,
            'service_date': date(2026, 11, 5),
            'meal_period': OrderDelivery.MealPeriod.LUNCH,
            'status': OrderDelivery.DeliveryStatus.DELIVERED,
        }
        defaults.update(kwargs)
        return OrderDelivery.objects.create(**defaults)

    def test_parse_window_defaults_to_dhaka_month(self):
        start, end, label = parse_analytics_window({})
        expected_start, expected_end = month_bounds_dhaka()
        self.assertEqual(start, expected_start)
        self.assertEqual(end, expected_end)
        self.assertIn('current_month', label)

    def test_parse_window_rejects_unknown_params(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_analytics_window({'from': '2026-11-01', 'to': '2026-11-30', 'foo': '1'})
        self.assertIn('query', ctx.exception.detail)

    def test_parse_window_rejects_invalid_date(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_analytics_window({'from': 'not-a-date', 'to': '2026-11-30'})
        self.assertIn('from', ctx.exception.detail)

    def test_parse_window_custom_inclusive(self):
        start, end, label = parse_analytics_window(
            {'from': '2026-11-01', 'to': '2026-11-15'}
        )
        self.assertEqual(start, date(2026, 11, 1))
        self.assertEqual(end, date(2026, 11, 15))
        self.assertEqual(label, '2026-11-01..2026-11-15')

    def test_consumption_counts_delivered_only(self):
        self._delivery(status=OrderDelivery.DeliveryStatus.DELIVERED)
        self._delivery(
            service_date=date(2026, 11, 6),
            meal_period=OrderDelivery.MealPeriod.DINNER,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
        )
        self._delivery(
            service_date=date(2026, 11, 7),
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.CUSTOMER,
        )
        self._delivery(
            service_date=date(2026, 11, 8),
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        section = build_consumption_section(
            self.customer, date(2026, 11, 1), date(2026, 11, 30)
        )
        self.assertEqual(section['lifetime_total'], 2)
        self.assertEqual(section['window_total'], 2)
        period_total = sum(item['count'] for item in section['by_meal_period'])
        self.assertEqual(period_total, 2)
        self.assertEqual(section['by_meal_type'][0]['key'], 'monthly')
        self.assertEqual(section['top_meals'][0]['label'], 'Regular Package')

    def test_consumption_empty_customer_zeros(self):
        empty = self._make_customer('empty-cust')
        section = build_consumption_section(empty, date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(section['lifetime_total'], 0)
        self.assertEqual(section['window_total'], 0)
        self.assertEqual(section['by_meal_period'], [])
        self.assertEqual(section['top_meals'], [])

    def test_meal_off_excludes_system_cutoff(self):
        self._delivery(
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.CUSTOMER,
        )
        self._delivery(
            service_date=date(2026, 11, 6),
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.SYSTEM,
            note=CUTOFF_PASSED_NOTE,
        )
        section = build_meal_off_section(
            self.customer, date(2026, 11, 1), date(2026, 11, 30)
        )
        self.assertEqual(section['lifetime_total'], 1)
        self.assertEqual(section['window_total'], 1)

    def test_blocked_estimate_labeled_and_unblocked_zero(self):
        self._delivery(
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.SYSTEM,
            note=CUTOFF_PASSED_NOTE,
        )
        section = build_blocked_low_balance_section(
            self.customer, date(2026, 11, 1), date(2026, 11, 30)
        )
        self.assertFalse(section['currently_blocked'])
        self.assertEqual(section['blocked_meals_estimate'], 1)
        self.assertEqual(section['note'], BLOCKED_ESTIMATE_NOTE)

        self.customer.meal_service_blocked_low_balance = True
        self.customer.meal_service_blocked_at = timezone.now()
        self.customer.save(update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at'])
        blocked = build_blocked_low_balance_section(
            self.customer, date(2026, 11, 1), date(2026, 11, 30)
        )
        self.assertTrue(blocked['currently_blocked'])
        self.assertIsNotNone(blocked['blocked_at'])

    def test_wallet_recharge_never_and_after_block(self):
        empty = build_wallet_recharge_section(
            self.customer, date(2026, 11, 1), date(2026, 11, 30)
        )
        self.assertEqual(empty['recharge_count'], 0)
        self.assertIsNone(empty['last_recharge_at'])
        self.assertEqual(empty['recent'], [])

        blocked_at = timezone.now() - timedelta(days=2)
        self.customer.meal_service_blocked_low_balance = True
        self.customer.meal_service_blocked_at = blocked_at
        self.customer.save(
            update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at']
        )
        WalletTransaction.objects.create(
            wallet=self.wallet,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            amount=Decimal('500.00'),
            status=WalletTransaction.Status.COMPLETED,
            method=WalletTransaction.Method.BKASH,
            reviewed_at=timezone.now(),
        )
        section = build_wallet_recharge_section(
            self.customer, date(2026, 11, 1), date(2026, 11, 30)
        )
        self.assertEqual(section['recharge_count'], 1)
        self.assertEqual(section['recharges_after_block_count'], 1)
        self.assertEqual(section['total_recharged'], '500.00')
        self.assertEqual(section['by_method'][0]['key'], 'bkash')

    def test_matrix_null_on_zero_denominator(self):
        consumption = {
            'lifetime_total': 0,
            'window_total': 0,
            'by_meal_period': [],
            'by_meal_type': [],
            'top_meals': [],
        }
        meal_off = {
            'lifetime_total': 0,
            'window_total': 0,
            'by_meal_period': [],
            'by_weekday': [],
            'top_off_meals_lifetime': [],
            'top_off_meals_window': [],
            'top_off_menus_window': [],
        }
        blocked = {
            'currently_blocked': False,
            'blocked_at': None,
            'blocked_meals_estimate': 0,
            'blocked_meals_window_estimate': 0,
            'note': BLOCKED_ESTIMATE_NOTE,
        }
        wallet = {
            'recharge_count': 0,
            'total_recharged': '0.00',
            'average_amount': None,
            'last_recharge_at': None,
            'on_time_count': 0,
            'recharges_after_block_count': 0,
            'median_gap_days': None,
            'by_method': [],
            'recent': [],
            'note': None,
        }
        matrix = build_matrix_section(
            consumption=consumption,
            meal_off=meal_off,
            blocked=blocked,
            wallet_recharge=wallet,
            start=date(2026, 11, 1),
            end=date(2026, 11, 30),
            customer=self.customer,
        )
        self.assertIsNone(matrix['delivery_rate'])
        self.assertIsNone(matrix['preference_off_rate'])
        self.assertIsNone(matrix['block_rate_estimate'])
        self.assertEqual(matrix['recharges_per_30d'], 0.0)

    def test_matrix_healthy_ratios(self):
        self._delivery(status=OrderDelivery.DeliveryStatus.DELIVERED)
        self._delivery(
            service_date=date(2026, 11, 6),
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.CUSTOMER,
        )
        payload = build_customer_analytics(
            self.customer, {'from': '2026-11-01', 'to': '2026-11-30'}
        )
        self.assertEqual(payload['timezone'], 'Asia/Dhaka')
        self.assertEqual(payload['consumption']['window_total'], 1)
        self.assertEqual(payload['meal_off']['window_total'], 1)
        self.assertIsNotNone(payload['matrix']['delivery_rate'])
        self.assertIsNotNone(payload['matrix']['preference_off_rate'])


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AdminCustomerAnalyticsAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin = User.objects.create_user(
            username='admin-analytics',
            email='admin-analytics@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin, is_verified=True)
        self.admin.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin)

        self.meal = MealCategory.objects.create(
            meal_name='Analytics Package',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('analytics-api-meal.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        user = User.objects.create_user(
            username='cust-analytics',
            email='cust-analytics@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        user.groups.add(self.customer_group)
        self.customer = CustomerProfile.objects.create(
            user=user,
            phone='1799999911',
            is_email_verified=True,
            is_phone_verified=True,
        )
        Wallet.objects.create(
            customer=self.customer,
            balance=Decimal('100.00'),
            recharge_balance=Decimal('100.00'),
        )
        self.subscription = CustomerSubscription.objects.create(
            customer=self.customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_period_snapshot=self.meal.meal_period,
            quantity=1,
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 1, 1),
        )
        OrderDelivery.objects.create(
            subscription=self.subscription,
            service_date=date(2026, 11, 5),
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
        )

    def _url(self, public_id=None):
        return reverse(
            'web_customers:admin-customer-analytics',
            kwargs={'public_id': public_id or self.customer.public_id},
        )

    def test_analytics_happy_path(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get(
            self._url(), {'from': '2026-11-01', 'to': '2026-11-30'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body['timezone'], 'Asia/Dhaka')
        self.assertIn('consumption', body)
        self.assertIn('meal_off', body)
        self.assertIn('blocked_low_balance', body)
        self.assertIn('wallet_recharge', body)
        self.assertIn('matrix', body)
        self.assertEqual(body['consumption']['window_total'], 1)
        self.assertEqual(body['window']['from'], '2026-11-01')
        self.assertEqual(body['window']['to'], '2026-11-30')

    def test_analytics_default_month_window(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        start, end = month_bounds_dhaka()
        self.assertEqual(response.json()['window']['from'], start.isoformat())
        self.assertEqual(response.json()['window']['to'], end.isoformat())

    def test_analytics_unknown_customer_404(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get(self._url(public_id=uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_analytics_unauthenticated_401(self):
        response = self.client.get(self._url())
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_analytics_non_admin_403(self):
        plain = User.objects.create_user(
            username='plain-user',
            email='plain@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        token = Token.objects.create(user=plain)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_analytics_unknown_query_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get(self._url(), {'from': '2026-11-01', 'to': '2026-11-30', 'foo': '1'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
