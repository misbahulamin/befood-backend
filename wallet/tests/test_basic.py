from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from user_management.models import CustomerProfile
from wallet.models import Wallet, WalletTransaction
from wallet.services.funding import request_recharge, request_withdraw
from wallet.services.ledger import (
    InsufficientFundsError,
    InvalidAmountError,
    WalletFrozenError,
    credit_wallet,
    debit_wallet,
    get_or_create_wallet,
)


def _make_customer(username='u1', phone='1711111111', verified=True):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    profile = CustomerProfile.objects.create(
        user=user,
        phone=phone,
        occupation=CustomerProfile.Occupation.STUDENT,
        is_bachelor=True,
        is_email_verified=verified,
    )
    return user, profile


class WalletLedgerTest(TestCase):
    def setUp(self):
        _, self.profile = _make_customer()
        self.wallet = get_or_create_wallet(self.profile)

    def test_credit_increases_balance_and_writes_ledger(self):
        txn = credit_wallet(self.wallet, Decimal('100.00'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100.00'))
        self.assertEqual(txn.direction, WalletTransaction.Direction.CREDIT)
        self.assertEqual(txn.amount, Decimal('100.00'))
        self.assertEqual(txn.balance_after, Decimal('100.00'))
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)

    def test_debit_decreases_balance_and_writes_ledger(self):
        credit_wallet(self.wallet, Decimal('100.00'))
        txn = debit_wallet(self.wallet, Decimal('40.00'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('60.00'))
        self.assertEqual(txn.direction, WalletTransaction.Direction.DEBIT)
        self.assertEqual(txn.balance_after, Decimal('60.00'))

    def test_debit_rejected_when_insufficient_funds(self):
        credit_wallet(self.wallet, Decimal('10.00'))
        with self.assertRaises(InsufficientFundsError):
            debit_wallet(self.wallet, Decimal('40.00'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('10.00'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                direction=WalletTransaction.Direction.DEBIT,
            ).count(),
            0,
        )

    def test_frozen_wallet_rejects_credit(self):
        self.wallet.status = Wallet.Status.FROZEN
        self.wallet.save(update_fields=['status'])
        with self.assertRaises(WalletFrozenError):
            credit_wallet(self.wallet, Decimal('10.00'))

    def test_invalid_amount_rejected(self):
        with self.assertRaises(InvalidAmountError):
            credit_wallet(self.wallet, Decimal('0'))
        with self.assertRaises(InvalidAmountError):
            credit_wallet(self.wallet, Decimal('-5'))
        with self.assertRaises(InvalidAmountError):
            credit_wallet(self.wallet, Decimal('1.234'))


class WalletAPITests(APITestCase):
    def setUp(self):
        self.user, self.profile = _make_customer(username='cust1', phone='1712345678')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.wallet_url = reverse('wallet:wallet-detail')
        self.recharge_url = reverse('wallet:wallet-recharge')
        self.withdraw_url = reverse('wallet:wallet-withdraw')
        self.txn_list_url = reverse('wallet:wallet-transaction-list')

    def test_get_wallet_creates_zero_balance(self):
        self.assertFalse(Wallet.objects.filter(customer=self.profile).exists())
        response = self.client.get(self.wallet_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance'], '0.00')
        self.assertEqual(response.data['currency'], 'BDT')
        self.assertEqual(response.data['status'], 'active')
        self.assertEqual(response.data['min_wallet_balance_to_order'], '500.00')
        self.assertEqual(response.data['low_balance_reminder_threshold'], '300.00')
        self.assertEqual(response.data['meal_stop_threshold'], '200.00')
        self.assertIn('public_id', response.data)
        self.assertNotIn('id', response.data)

    def test_unauthenticated_wallet_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.wallet_url)
        self.assertEqual(response.status_code, 401)

    def test_customer_cannot_see_other_wallet(self):
        other_user, other_profile = _make_customer(username='cust2', phone='1712345679')
        other_wallet = get_or_create_wallet(other_profile)
        credit_wallet(other_wallet, Decimal('999.00'))

        response = self.client.get(self.wallet_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance'], '0.00')
        self.assertNotEqual(str(response.data['public_id']), str(other_wallet.public_id))

    def test_successful_recharge_pending(self):
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '500.00',
                'payment_method': 'bkash',
                'transaction_id': 'CASH-1',
                'note': 'Cash top-up',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['wallet']['balance'], '0.00')
        self.assertEqual(response.data['transaction']['type'], 'recharge')
        self.assertEqual(response.data['transaction']['direction'], 'credit')
        self.assertEqual(response.data['transaction']['method'], 'bkash')
        self.assertEqual(response.data['transaction']['status'], 'pending')

    def test_successful_withdraw_reserves(self):
        credit_wallet(get_or_create_wallet(self.profile), Decimal('500.00'))
        response = self.client.post(
            self.withdraw_url,
            {'amount': '500.00'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['wallet']['balance'], '0.00')
        self.assertEqual(response.data['transaction']['type'], 'withdraw')
        self.assertEqual(response.data['transaction']['direction'], 'debit')
        self.assertEqual(response.data['transaction']['method'], 'manual')
        self.assertEqual(response.data['transaction']['status'], 'pending')

    def test_invalid_recharge_amount(self):
        for bad in ('0', '-10', '1.234'):
            response = self.client.post(
                self.recharge_url,
                {
                    'amount': bad,
                    'payment_method': 'bkash',
                    'transaction_id': f'bad-{bad}',
                },
                format='json',
            )
            self.assertIn(response.status_code, (400, 422))
            wallet = Wallet.objects.filter(customer=self.profile).first()
            if wallet is not None:
                self.assertEqual(wallet.balance, Decimal('0.00'))

    def test_frozen_wallet_cannot_recharge(self):
        wallet = get_or_create_wallet(self.profile)
        wallet.status = Wallet.Status.FROZEN
        wallet.save(update_fields=['status'])
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'FROZEN-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('0.00'))

    def test_withdraw_exceeds_balance(self):
        credit_wallet(get_or_create_wallet(self.profile), Decimal('50.00'))
        response = self.client.post(self.withdraw_url, {'amount': '100.00'}, format='json')
        self.assertEqual(response.status_code, 400)
        wallet = Wallet.objects.get(customer=self.profile)
        self.assertEqual(wallet.balance, Decimal('50.00'))

    def test_unauthenticated_recharge_returns_401(self):
        self.client.credentials()
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'UAUTH-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_idempotency_replay_does_not_double_create(self):
        payload = {
            'amount': '100.00',
            'payment_method': 'bkash',
            'transaction_id': 'IDEM-API-1',
            'idempotency_key': 'key-abc',
        }
        first = self.client.post(self.recharge_url, payload, format='json')
        second = self.client.post(self.recharge_url, payload, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['transaction']['public_id'], second.data['transaction']['public_id'])
        wallet = Wallet.objects.get(customer=self.profile)
        self.assertEqual(wallet.balance, Decimal('0.00'))
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet).count(), 1)

    def test_idempotency_conflict_on_different_amount(self):
        self.client.post(
            self.recharge_url,
            {
                'amount': '100.00',
                'payment_method': 'bkash',
                'transaction_id': 'IDEM-API-2',
                'idempotency_key': 'key-xyz',
            },
            format='json',
        )
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '200.00',
                'payment_method': 'bkash',
                'transaction_id': 'IDEM-API-3',
                'idempotency_key': 'key-xyz',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 409)

    def test_idempotency_header(self):
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '25.00',
                'payment_method': 'nagad',
                'transaction_id': 'HDR-1',
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='hdr-1',
        )
        self.assertEqual(response.status_code, 200)
        replay = self.client.post(
            self.recharge_url,
            {
                'amount': '25.00',
                'payment_method': 'nagad',
                'transaction_id': 'HDR-1',
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='hdr-1',
        )
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(
            response.data['transaction']['public_id'],
            replay.data['transaction']['public_id'],
        )

    def test_transaction_list_and_detail(self):
        request_recharge(
            self.profile,
            Decimal('30.00'),
            payment_method='bkash',
            transaction_id='LIST-R',
        )
        credit_wallet(get_or_create_wallet(self.profile), Decimal('30.00'))
        request_withdraw(self.profile, Decimal('10.00'))
        list_response = self.client.get(self.txn_list_url)
        self.assertEqual(list_response.status_code, 200)
        results = list_response.data['results'] if 'results' in list_response.data else list_response.data
        self.assertGreaterEqual(len(results), 2)

        public_id = results[0]['public_id']
        detail_url = reverse('wallet:wallet-transaction-detail', kwargs={'public_id': public_id})
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['public_id'], public_id)

    def test_foreign_transaction_public_id_returns_404(self):
        other_user, other_profile = _make_customer(username='cust3', phone='1712345680')
        other_wallet = get_or_create_wallet(other_profile)
        txn = credit_wallet(other_wallet, Decimal('5.00'))
        detail_url = reverse(
            'wallet:wallet-transaction-detail',
            kwargs={'public_id': str(txn.public_id)},
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

    @override_settings(WALLET_MANUAL_FUNDING_ENABLED=False)
    def test_manual_funding_disabled(self):
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'DISABLED-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)
