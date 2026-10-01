"""Minimum recharge amount: boundary, admin update, auth, pending-unaffected."""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from orders.models import OrderWalletSettings
from orders.services.order_wallet_settings import update_order_wallet_settings
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import WalletTransaction
from wallet.services.funding import RechargeBelowMinimumError, request_recharge


def _make_customer(username='minrc', phone='1700000011'):
    user = User.objects.create_user(
        username=username, email=f'{username}@example.com', password='StrongPassword123'
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
    return profile


def _make_admin(username='minradmin'):
    user = User.objects.create_user(
        username=username, email=f'{username}@example.com', password='StrongPassword123'
    )
    group, _ = Group.objects.get_or_create(name='ADMIN')
    user.groups.add(group)
    AdminProfile.objects.create(user=user, is_verified=True)
    return user


def _recharge(customer, amount, ref):
    return request_recharge(
        customer,
        Decimal(amount),
        payment_method='bkash',
        transaction_id=ref,
        idempotency_key=f'key-{ref}',
    )


class MinimumRechargeTests(TestCase):
    def setUp(self):
        self.customer = _make_customer()
        OrderWalletSettings.load()
        update_order_wallet_settings(minimum_recharge_amount=Decimal('500.00'))

    def test_default_is_500(self):
        self.assertEqual(
            OrderWalletSettings.load().minimum_recharge_amount, Decimal('500.00')
        )

    def test_boundary(self):
        with self.assertRaises(RechargeBelowMinimumError) as ctx:
            _recharge(self.customer, '499.99', 'min-r1')
        self.assertEqual(ctx.exception.code, 'RECHARGE_BELOW_MINIMUM')
        _, txn_ok, _ = _recharge(self.customer, '500.00', 'min-r2')
        self.assertEqual(txn_ok.status, WalletTransaction.Status.PENDING)
        _, txn_above, _ = _recharge(self.customer, '500.01', 'min-r3')
        self.assertEqual(txn_above.status, WalletTransaction.Status.PENDING)

    def test_admin_update_immediate(self):
        update_order_wallet_settings(minimum_recharge_amount=Decimal('700.00'))
        with self.assertRaises(RechargeBelowMinimumError):
            _recharge(self.customer, '600.00', 'min-r4')
        _, txn, _ = _recharge(self.customer, '700.00', 'min-r5')
        self.assertEqual(txn.status, WalletTransaction.Status.PENDING)

    def test_invalid_admin_values(self):
        from django.core.exceptions import ValidationError

        for bad in ('-1', '10.123', 'not-a-number'):
            with self.assertRaises((ValidationError, Exception)):
                from orders.services.order_wallet_settings import parse_decimal_amount

                update_order_wallet_settings(
                    minimum_recharge_amount=parse_decimal_amount(bad)
                )

    def test_old_pending_untouched(self):
        _, txn, _ = _recharge(self.customer, '500.00', 'min-r6')
        update_order_wallet_settings(minimum_recharge_amount=Decimal('900.00'))
        txn.refresh_from_db()
        self.assertEqual(txn.status, WalletTransaction.Status.PENDING)
        self.assertEqual(txn.amount, Decimal('500.00'))

    def test_api_error_contract_and_auth(self):
        from django.urls import reverse

        c = APIClient()
        c.force_authenticate(user=self.customer.user)
        resp = c.post(
            reverse('wallet:wallet-recharge'),
            {'amount': '100.00', 'payment_method': 'bkash', 'transaction_id': 'api-min-1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'RECHARGE_BELOW_MINIMUM')
        self.assertEqual(resp.data['minimum_recharge_amount'], '500.00')

        anon = APIClient()
        resp2 = anon.patch(
            '/api/v1/web/orders/order-wallet-settings/',
            {'minimum_recharge_amount': '600.00'},
            format='json',
        )
        self.assertIn(resp2.status_code, (401, 403))

        admin = _make_admin()
        ac = APIClient()
        ac.force_authenticate(user=admin)
        resp3 = ac.patch(
            '/api/v1/web/orders/order-wallet-settings/',
            {'minimum_recharge_amount': '600.00'},
            format='json',
        )
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3.data['minimum_recharge_amount'], '600.00')
