"""Tests for admin manual delivery-fee wallet deduction."""

from decimal import Decimal
from datetime import date
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.services.ledger import get_or_create_platform_wallet
from meals.models import MealCategory
from notifications.models import Notification
from orders.models import CustomerSubscription
from orders.services.meal_payment import MEAL_DELIVERY_PURPOSE
from user_management.models import AdminProfile, CustomerProfile
from wallet.api.serializers import WalletTransactionSerializer
from wallet.models import DeliveryFeePayment, Wallet, WalletTransaction
from wallet.services.delivery_fee import (
    DeliveryFeeAlreadyPaidError,
    charge_delivery_fee,
)
from wallet.services.ledger import (
    InsufficientFundsError,
    WalletFrozenError,
    credit_wallet,
    get_or_create_wallet,
)


def _make_meal(name='Fee Package'):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = BytesIO()
    Image.new('RGB', (10, 10), color='red').save(buffer, format='JPEG')
    image = SimpleUploadedFile(
        f'{name.lower().replace(" ", "-")}.jpg',
        buffer.getvalue(),
        content_type='image/jpeg',
    )
    return MealCategory.objects.create(
        meal_name=name,
        total_price=Decimal('2737.00'),
        meal_thumbnail=image,
        meal_type=MealCategory.MealType.MONTHLY,
        meal_period=MealCategory.MealPeriod.BOTH,
        is_active=True,
        is_subscribable=True,
    )


def _make_customer(username='fee_cust', phone='1712345678'):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        first_name='Rahim',
        last_name='Ahmed',
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    profile = CustomerProfile.objects.create(
        user=user,
        phone=phone,
        occupation=CustomerProfile.Occupation.STUDENT,
        is_bachelor=True,
        is_email_verified=True,
    )
    return user, profile


def _make_admin(username='fee_admin'):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        first_name='Shohan',
        is_active=True,
    )
    group, _ = Group.objects.get_or_create(name='ADMIN')
    user.groups.add(group)
    profile = AdminProfile.objects.create(user=user, is_verified=True)
    return user, profile


class DeliveryFeeServiceTests(TestCase):
    def setUp(self):
        self.user, self.customer = _make_customer()
        self.admin_user, self.admin = _make_admin()
        self.wallet = get_or_create_wallet(self.customer)
        credit_wallet(
            self.wallet,
            Decimal('1250.00'),
            type=WalletTransaction.Type.RECHARGE,
            method=WalletTransaction.Method.MANUAL,
            status=WalletTransaction.Status.COMPLETED,
            note='seed',
        )
        self.wallet.refresh_from_db()
        self.platform = get_or_create_platform_wallet()
        self.platform_balance_before = self.platform.balance

    def test_successful_deduct_creates_payment_and_debit(self):
        with self.captureOnCommitCallbacks(execute=True):
            payment, created = charge_delivery_fee(
                self.customer,
                Decimal('300.00'),
                payment_month=9,
                payment_year=2026,
                reason='September Delivery Fee',
                actor_admin=self.admin,
                idempotency_key='fee-key-1',
            )
        self.assertTrue(created)
        self.assertEqual(payment.status, DeliveryFeePayment.Status.PAID)
        self.assertEqual(payment.amount, Decimal('300.00'))
        self.assertEqual(payment.source, DeliveryFeePayment.Source.MANUAL)
        txn = payment.wallet_transaction
        self.assertEqual(txn.type, WalletTransaction.Type.DELIVERY_FEE_PAYMENT)
        self.assertEqual(txn.direction, WalletTransaction.Direction.DEBIT)
        self.assertEqual(txn.amount, Decimal('300.00'))
        self.assertEqual(txn.reviewed_by_id, self.admin_user.pk)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('950.00'))

    def test_insufficient_balance_rejected(self):
        with self.assertRaises(InsufficientFundsError) as ctx:
            charge_delivery_fee(
                self.customer,
                Decimal('2000.00'),
                payment_month=9,
                payment_year=2026,
                reason='September Delivery Fee',
                actor_admin=self.admin,
            )
        self.assertIn('Insufficient wallet balance', str(ctx.exception))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1250.00'))
        self.assertEqual(DeliveryFeePayment.objects.count(), 0)

    def test_frozen_wallet_rejected(self):
        self.wallet.status = Wallet.Status.FROZEN
        self.wallet.save(update_fields=['status', 'updated_at'])
        with self.assertRaises(WalletFrozenError):
            charge_delivery_fee(
                self.customer,
                Decimal('300.00'),
                payment_month=9,
                payment_year=2026,
                reason='September Delivery Fee',
                actor_admin=self.admin,
            )
        self.assertEqual(DeliveryFeePayment.objects.count(), 0)

    def test_duplicate_month_rejected(self):
        charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=9,
            payment_year=2026,
            reason='September Delivery Fee',
            actor_admin=self.admin,
            idempotency_key='fee-dup-a',
        )
        with self.assertRaises(DeliveryFeeAlreadyPaidError):
            charge_delivery_fee(
                self.customer,
                Decimal('300.00'),
                payment_month=9,
                payment_year=2026,
                reason='September Delivery Fee again',
                actor_admin=self.admin,
                idempotency_key='fee-dup-b',
            )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('950.00'))
        self.assertEqual(DeliveryFeePayment.objects.count(), 1)

    def test_idempotent_key_replay_safe(self):
        payment1, created1 = charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=9,
            payment_year=2026,
            reason='September Delivery Fee',
            actor_admin=self.admin,
            idempotency_key='fee-idem-1',
        )
        payment2, created2 = charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=9,
            payment_year=2026,
            reason='September Delivery Fee',
            actor_admin=self.admin,
            idempotency_key='fee-idem-1',
        )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(payment1.pk, payment2.pk)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('950.00'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.DELIVERY_FEE_PAYMENT
            ).count(),
            1,
        )

    def test_admin_wallet_cash_unchanged(self):
        charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=9,
            payment_year=2026,
            reason='September Delivery Fee',
            actor_admin=self.admin,
        )
        self.platform.refresh_from_db()
        self.assertEqual(self.platform.balance, self.platform_balance_before)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DeliveryFeeNotificationTests(TestCase):
    def setUp(self):
        self.user, self.customer = _make_customer(username='fee_notify')
        self.admin_user, self.admin = _make_admin(username='fee_notify_admin')
        self.wallet = get_or_create_wallet(self.customer)
        credit_wallet(
            self.wallet,
            Decimal('1000.00'),
            type=WalletTransaction.Type.RECHARGE,
            status=WalletTransaction.Status.COMPLETED,
        )

    def test_inbox_created_on_success(self):
        with self.captureOnCommitCallbacks(execute=True):
            with mock.patch(
                'wallet.services.delivery_fee_notifications.send_to_tokens'
            ) as send_mock:
                send_mock.return_value = None
                with mock.patch(
                    'wallet.services.delivery_fee_notifications.get_user_device_tokens',
                    return_value=['tok'],
                ):
                    charge_delivery_fee(
                        self.customer,
                        Decimal('300.00'),
                        payment_month=9,
                        payment_year=2026,
                        reason='September Delivery Fee',
                        actor_admin=self.admin,
                    )
        note = Notification.objects.filter(
            user=self.user,
            notification_type='delivery_fee_deducted',
        ).first()
        self.assertIsNotNone(note)
        self.assertIn('300', note.body)
        self.assertIn('September', note.body)

    def test_debit_remains_if_fcm_fails(self):
        with self.captureOnCommitCallbacks(execute=True):
            with mock.patch(
                'wallet.services.delivery_fee_notifications.get_user_device_tokens',
                return_value=['tok'],
            ):
                with mock.patch(
                    'wallet.services.delivery_fee_notifications.send_to_tokens',
                    side_effect=RuntimeError('fcm down'),
                ):
                    payment, _ = charge_delivery_fee(
                        self.customer,
                        Decimal('300.00'),
                        payment_month=9,
                        payment_year=2026,
                        reason='September Delivery Fee',
                        actor_admin=self.admin,
                    )
        payment.refresh_from_db()
        self.assertEqual(payment.status, DeliveryFeePayment.Status.PAID)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('700.00'))


class DeliveryFeeSerializerHistoryTests(TestCase):
    def setUp(self):
        self.user, self.customer = _make_customer(username='fee_hist')
        self.admin_user, self.admin = _make_admin(username='fee_hist_admin')
        self.wallet = get_or_create_wallet(self.customer)
        credit_wallet(
            self.wallet,
            Decimal('1000.00'),
            type=WalletTransaction.Type.RECHARGE,
            status=WalletTransaction.Status.COMPLETED,
        )

    def test_delivery_fee_context_present_meal_unchanged(self):
        payment, _ = charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=9,
            payment_year=2026,
            reason='September Delivery Fee',
            actor_admin=self.admin,
        )
        fee_data = WalletTransactionSerializer(payment.wallet_transaction).data
        self.assertEqual(fee_data['type'], 'delivery_fee_payment')
        self.assertIsNone(fee_data['meal_payment'])
        self.assertIsNotNone(fee_data['delivery_fee'])
        self.assertEqual(fee_data['delivery_fee']['payment_month'], 9)
        self.assertEqual(fee_data['delivery_fee']['payment_year'], 2026)

        meal_txn = WalletTransaction.objects.create(
            wallet=self.wallet,
            type=WalletTransaction.Type.PAYMENT,
            direction=WalletTransaction.Direction.DEBIT,
            amount=Decimal('62.00'),
            balance_after=Decimal('638.00'),
            status=WalletTransaction.Status.COMPLETED,
            method=WalletTransaction.Method.MANUAL,
            note='Meal payment lunch',
            metadata={
                'purpose': MEAL_DELIVERY_PURPOSE,
                'meal_name': 'Premium',
                'service_date': '2026-09-01',
                'meal_period': 'lunch',
                'order_public_id': '11111111-1111-1111-1111-111111111111',
                'delivery_public_id': '22222222-2222-2222-2222-222222222222',
            },
        )
        meal_data = WalletTransactionSerializer(meal_txn).data
        self.assertEqual(meal_data['type'], 'payment')
        self.assertIsNotNone(meal_data['meal_payment'])
        self.assertIsNone(meal_data['delivery_fee'])
        self.assertEqual(meal_data['meal_payment']['meal_period'], 'lunch')


class DeliveryFeeApiTests(APITestCase):
    def setUp(self):
        self.user, self.customer = _make_customer(username='fee_api')
        self.admin_user, self.admin = _make_admin(username='fee_api_admin')
        self.wallet = get_or_create_wallet(self.customer)
        credit_wallet(
            self.wallet,
            Decimal('1250.00'),
            type=WalletTransaction.Type.RECHARGE,
            status=WalletTransaction.Status.COMPLETED,
        )
        self.admin_token = Token.objects.create(user=self.admin_user)
        self.customer_token = Token.objects.create(user=self.user)
        self.context_url = reverse(
            'web_customers:admin-customer-delivery-fee-context',
            kwargs={'public_id': self.customer.public_id},
        )
        self.payments_url = reverse(
            'web_customers:admin-customer-delivery-fee-payments',
            kwargs={'public_id': self.customer.public_id},
        )
        self.monthly_url = reverse('web_delivery_fees:report-monthly')
        self.lifetime_url = reverse('web_delivery_fees:report-lifetime')
        self.list_url = reverse('web_delivery_fees:payment-list')

    def test_verified_admin_can_deduct(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.post(
            self.payments_url,
            {
                'amount': '300.00',
                'payment_month': 9,
                'payment_year': 2026,
                'reason': 'September Delivery Fee',
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='api-fee-1',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['amount'], '300.00')
        self.assertEqual(response.data['status'], 'paid')

    def test_customer_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        response = self.client.post(
            self.payments_url,
            {
                'amount': '300.00',
                'payment_month': 9,
                'payment_year': 2026,
                'reason': 'September Delivery Fee',
            },
            format='json',
        )
        self.assertIn(response.status_code, (403, 401))
        self.assertEqual(DeliveryFeePayment.objects.count(), 0)

    def test_unauthenticated_denied(self):
        response = self.client.get(self.context_url)
        self.assertEqual(response.status_code, 401)

    def test_context_and_history(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=8,
            payment_year=2026,
            reason='August Delivery Fee',
            actor_admin=self.admin,
        )
        ctx = self.client.get(self.context_url)
        self.assertEqual(ctx.status_code, 200)
        self.assertEqual(ctx.data['wallet_balance'], '950.00')
        self.assertTrue(len(ctx.data['delivery_fee_history']) >= 1)

        hist = self.client.get(self.payments_url)
        self.assertEqual(hist.status_code, 200)
        self.assertGreaterEqual(hist.data['count'], 1)

    def test_insufficient_balance_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.post(
            self.payments_url,
            {
                'amount': '5000.00',
                'payment_month': 9,
                'payment_year': 2026,
                'reason': 'September Delivery Fee',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Insufficient wallet balance', response.data['detail'])

    def test_duplicate_month_conflict(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        body = {
            'amount': '300.00',
            'payment_month': 9,
            'payment_year': 2026,
            'reason': 'September Delivery Fee',
        }
        first = self.client.post(
            self.payments_url, body, format='json', HTTP_IDEMPOTENCY_KEY='dup-1'
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            self.payments_url, body, format='json', HTTP_IDEMPOTENCY_KEY='dup-2'
        )
        self.assertEqual(second.status_code, 409)

    def test_monthly_and_lifetime_reports(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        meal = _make_meal()
        # Active subscriber without payment → pending
        CustomerSubscription.objects.create(
            customer=self.customer,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_period_snapshot=meal.meal_period,
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 1, 1),
        )
        # Second paid customer
        _, other = _make_customer(username='fee_other', phone='1811111111')
        other_wallet = get_or_create_wallet(other)
        credit_wallet(
            other_wallet,
            Decimal('500.00'),
            type=WalletTransaction.Type.RECHARGE,
            status=WalletTransaction.Status.COMPLETED,
        )
        CustomerSubscription.objects.create(
            customer=other,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_period_snapshot=meal.meal_period,
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 1, 1),
        )
        charge_delivery_fee(
            self.customer,
            Decimal('300.00'),
            payment_month=9,
            payment_year=2026,
            reason='September Delivery Fee',
            actor_admin=self.admin,
        )

        empty = self.client.get(self.monthly_url, {'year': 2025, 'month': 1})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.data['total_collected'], '0.00')
        self.assertEqual(empty.data['customers_paid'], 0)
        self.assertEqual(empty.data['pending_customers'], 2)

        monthly = self.client.get(self.monthly_url, {'year': 2026, 'month': 9})
        self.assertEqual(monthly.status_code, 200)
        self.assertEqual(monthly.data['total_collected'], '300.00')
        self.assertEqual(monthly.data['customers_paid'], 1)
        self.assertEqual(monthly.data['pending_customers'], 1)

        lifetime = self.client.get(self.lifetime_url)
        self.assertEqual(lifetime.status_code, 200)
        self.assertEqual(lifetime.data['total_collected'], '300.00')
        self.assertEqual(lifetime.data['customers_paid'], 1)

    def test_unsupported_list_filter_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.get(self.list_url, {'foo': 'bar'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error_code'], 'UNSUPPORTED_FILTER')

    def test_customer_denied_reports(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        response = self.client.get(self.monthly_url, {'year': 2026, 'month': 9})
        self.assertIn(response.status_code, (403, 401))
