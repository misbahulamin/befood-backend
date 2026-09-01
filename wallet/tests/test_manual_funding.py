from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ledger import get_or_create_platform_wallet
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import Wallet, WalletTransaction
from wallet.services.funding import (
    DuplicateProviderRefError,
    FundingRequestConflictError,
    approve_recharge,
    approve_withdraw,
    reject_recharge,
    reject_withdraw,
    request_recharge,
    request_withdraw,
)
from wallet.services.ledger import (
    IdempotencyConflictError,
    InsufficientFundsError,
    PlatformFloatError,
    credit_wallet,
    get_or_create_wallet,
)
from wallet.services.ledger import MAX_FUNDING_AMOUNT


def _make_customer(username='u1', phone='1711111111', verified=True):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        first_name='Test',
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


def _make_admin(username='admin1', *, with_profile=True):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        is_active=True,
    )
    group, _ = Group.objects.get_or_create(name='ADMIN')
    user.groups.add(group)
    if with_profile:
        AdminProfile.objects.create(user=user, is_verified=True)
    return user


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ManualFundingServiceTests(TestCase):
    def setUp(self):
        self.user, self.profile = _make_customer()
        self.admin = _make_admin()
        self.wallet = get_or_create_wallet(self.profile)
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('10000.00')
        platform.save(update_fields=['balance', 'updated_at'])

    def test_request_recharge_pending_no_balance_change(self):
        with self.captureOnCommitCallbacks(execute=True):
            wallet, txn, created = request_recharge(
                self.profile,
                Decimal('100.00'),
                payment_method='bkash',
                transaction_id=' TX-1 ',
            )
        self.assertTrue(created)
        self.assertEqual(txn.status, WalletTransaction.Status.PENDING)
        self.assertEqual(txn.method, 'bkash')
        self.assertEqual(txn.external_ref, 'TX-1')
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('0.00'))
        self.assertEqual(len(mail.outbox), 1)

    def test_duplicate_provider_ref_rejected(self):
        request_recharge(
            self.profile,
            Decimal('10.00'),
            payment_method='nagad',
            transaction_id='DUP-1',
        )
        with self.assertRaises(DuplicateProviderRefError):
            request_recharge(
                self.profile,
                Decimal('20.00'),
                payment_method='nagad',
                transaction_id='DUP-1',
            )

    def test_approve_recharge_credits_once(self):
        _, txn, _ = request_recharge(
            self.profile,
            Decimal('50.00'),
            payment_method='bank',
            transaction_id='BANK-1',
        )
        approve_recharge(txn, reviewed_by=self.admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('50.00'))
        txn.refresh_from_db()
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)
        self.assertEqual(txn.reviewed_by_id, self.admin.pk)
        with self.assertRaises(FundingRequestConflictError):
            approve_recharge(txn, reviewed_by=self.admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('50.00'))

    def test_reject_recharge_no_credit(self):
        _, txn, _ = request_recharge(
            self.profile,
            Decimal('50.00'),
            payment_method='bkash',
            transaction_id='RJ-1',
        )
        reject_recharge(txn, reviewed_by=self.admin, reason='Invalid trx')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('0.00'))
        txn.refresh_from_db()
        self.assertEqual(txn.status, WalletTransaction.Status.FAILED)
        self.assertEqual(txn.rejection_reason, 'Invalid trx')

    def test_withdraw_reserves_and_reject_releases(self):
        credit_wallet(self.wallet, Decimal('200.00'))
        with self.captureOnCommitCallbacks(execute=True):
            wallet, txn, created = request_withdraw(self.profile, Decimal('80.00'))
        self.assertTrue(created)
        self.assertEqual(txn.method, WalletTransaction.Method.MANUAL)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('120.00'))
        self.assertEqual(len(mail.outbox), 1)
        reject_withdraw(txn, reviewed_by=self.admin)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('200.00'))

    def test_withdraw_approve_debits_custody(self):
        credit_wallet(self.wallet, Decimal('100.00'))
        _, txn, _ = request_withdraw(self.profile, Decimal('40.00'))
        before = get_or_create_platform_wallet().balance
        approve_withdraw(txn, reviewed_by=self.admin)
        txn.refresh_from_db()
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)
        self.assertEqual(
            get_or_create_platform_wallet().balance,
            before - Decimal('40.00'),
        )
        self.assertTrue(
            AdminWalletTransaction.objects.filter(
                type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
                customer_wallet_transaction=txn,
            ).exists()
        )

    def test_float_shortfall_non_mutating(self):
        credit_wallet(self.wallet, Decimal('50.00'))
        _, txn, _ = request_withdraw(self.profile, Decimal('25.00'))
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('0.00')
        platform.save(update_fields=['balance', 'updated_at'])
        with self.assertRaises(PlatformFloatError):
            approve_withdraw(txn, reviewed_by=self.admin)
        txn.refresh_from_db()
        self.assertEqual(txn.status, WalletTransaction.Status.PENDING)
        self.assertIsNone(txn.reviewed_by_id)
        self.assertIsNone(txn.reviewed_at)
        self.assertEqual(txn.rejection_reason, '')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('25.00'))

    def test_idempotency_recharge_replay_and_conflict(self):
        _, first, created = request_recharge(
            self.profile,
            Decimal('10.00'),
            payment_method='bkash',
            transaction_id='IDEM-1',
            idempotency_key='k1',
        )
        self.assertTrue(created)
        _, second, created2 = request_recharge(
            self.profile,
            Decimal('10.00'),
            payment_method='bkash',
            transaction_id='IDEM-1',
            idempotency_key='k1',
        )
        self.assertFalse(created2)
        self.assertEqual(first.public_id, second.public_id)
        with self.assertRaises(IdempotencyConflictError):
            request_recharge(
                self.profile,
                Decimal('11.00'),
                payment_method='bkash',
                transaction_id='IDEM-2',
                idempotency_key='k1',
            )

    def test_idempotency_cross_type_conflict(self):
        credit_wallet(self.wallet, Decimal('50.00'))
        request_recharge(
            self.profile,
            Decimal('10.00'),
            payment_method='bkash',
            transaction_id='XTYPE-1',
            idempotency_key='shared-key',
        )
        with self.assertRaises(IdempotencyConflictError):
            request_withdraw(
                self.profile,
                Decimal('10.00'),
                idempotency_key='shared-key',
            )

    def test_idempotency_replay_after_approve(self):
        _, txn, _ = request_recharge(
            self.profile,
            Decimal('15.00'),
            payment_method='bkash',
            transaction_id='AFTER-1',
            idempotency_key='after-key',
        )
        approve_recharge(txn, reviewed_by=self.admin)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            _, replay, created = request_recharge(
                self.profile,
                Decimal('15.00'),
                payment_method='bkash',
                transaction_id='AFTER-1',
                idempotency_key='after-key',
            )
        self.assertFalse(created)
        self.assertEqual(replay.status, WalletTransaction.Status.COMPLETED)
        self.assertEqual(replay.public_id, txn.public_id)
        self.assertEqual(len(mail.outbox), 0)

    def test_withdraw_idempotency_after_reservation(self):
        credit_wallet(self.wallet, Decimal('100.00'))
        _, first, _ = request_withdraw(
            self.profile,
            Decimal('60.00'),
            idempotency_key='w-key',
        )
        _, second, created = request_withdraw(
            self.profile,
            Decimal('60.00'),
            idempotency_key='w-key',
        )
        self.assertFalse(created)
        self.assertEqual(first.public_id, second.public_id)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('40.00'))

    def test_withdraw_above_max(self):
        credit_wallet(self.wallet, MAX_FUNDING_AMOUNT)
        from wallet.services.ledger import InvalidAmountError

        with self.assertRaises(InvalidAmountError):
            request_withdraw(self.profile, MAX_FUNDING_AMOUNT + Decimal('1.00'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, MAX_FUNDING_AMOUNT)

    def test_frozen_after_pending_still_resolvable(self):
        credit_wallet(self.wallet, Decimal('100.00'))
        _, wtxn, _ = request_withdraw(self.profile, Decimal('30.00'))
        _, rtxn, _ = request_recharge(
            self.profile,
            Decimal('20.00'),
            payment_method='bkash',
            transaction_id='FRZ-1',
        )
        self.wallet.status = Wallet.Status.FROZEN
        self.wallet.save(update_fields=['status'])
        reject_withdraw(wtxn, reviewed_by=self.admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100.00'))
        approve_recharge(rtxn, reviewed_by=self.admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('120.00'))

    def test_email_failure_keeps_pending(self):
        with mock.patch(
            'wallet.services.funding_notifications.notify_admins_pending_recharge',
            side_effect=RuntimeError('smtp down'),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                _, txn, created = request_recharge(
                    self.profile,
                    Decimal('5.00'),
                    payment_method='bkash',
                    transaction_id='SMTP-1',
                )
        self.assertTrue(created)
        txn.refresh_from_db()
        self.assertEqual(txn.status, WalletTransaction.Status.PENDING)

    def test_superuser_without_profile_can_approve(self):
        superuser = User.objects.create_superuser(
            username='su1',
            email='su1@example.com',
            password='StrongPassword123',
        )
        _, txn, _ = request_recharge(
            self.profile,
            Decimal('12.00'),
            payment_method='bkash',
            transaction_id='SU-1',
        )
        approve_recharge(txn, reviewed_by=superuser)
        txn.refresh_from_db()
        self.assertEqual(txn.reviewed_by_id, superuser.pk)

    def test_historical_manual_completed_row_ok_with_constraint(self):
        # Manual completed recharge with a ref must not collide with provider uniqueness.
        WalletTransaction.objects.create(
            wallet=self.wallet,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            amount=Decimal('1.00'),
            balance_after=Decimal('1.00'),
            status=WalletTransaction.Status.COMPLETED,
            method=WalletTransaction.Method.MANUAL,
            external_ref='LEGACY-REF',
        )
        _, txn, _ = request_recharge(
            self.profile,
            Decimal('2.00'),
            payment_method='bkash',
            transaction_id='LEGACY-REF',
        )
        self.assertEqual(txn.external_ref, 'LEGACY-REF')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ManualFundingAPITests(APITestCase):
    def setUp(self):
        self.user, self.profile = _make_customer(username='cust_api', phone='1799999999')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.recharge_url = reverse('wallet:wallet-recharge')
        self.withdraw_url = reverse('wallet:wallet-withdraw')
        self.admin = _make_admin(username='funding_admin')
        self.admin_token = Token.objects.create(user=self.admin)
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('5000.00')
        platform.save(update_fields=['balance', 'updated_at'])

    def test_customer_recharge_and_admin_approve(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.recharge_url,
                {
                    'amount': '100.00',
                    'payment_method': 'bkash',
                    'transaction_id': 'API-TX-1',
                },
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['transaction']['status'], 'pending')
        self.assertEqual(response.data['wallet']['balance'], '0.00')
        self.assertEqual(response.data['transaction']['transaction_id'], 'API-TX-1')
        public_id = response.data['transaction']['public_id']

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        approve_url = reverse(
            'web_wallet_funding:funding-request-approve',
            kwargs={'public_id': public_id},
        )
        approved = self.client.post(approve_url)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.data['status'], 'completed')

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        wallet = self.client.get(reverse('wallet:wallet-detail'))
        self.assertEqual(wallet.data['balance'], '100.00')

    def test_non_admin_cannot_approve(self):
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'NA-1',
            },
            format='json',
        )
        public_id = response.data['transaction']['public_id']
        approve_url = reverse(
            'web_wallet_funding:funding-request-approve',
            kwargs={'public_id': public_id},
        )
        forbidden = self.client.post(approve_url)
        self.assertEqual(forbidden.status_code, 403)

    def test_kill_switch_blocks_create_not_admin_resolve(self):
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'KS-1',
            },
            format='json',
        )
        public_id = response.data['transaction']['public_id']
        with override_settings(WALLET_MANUAL_FUNDING_ENABLED=False):
            blocked = self.client.post(
                self.recharge_url,
                {
                    'amount': '10.00',
                    'payment_method': 'bkash',
                    'transaction_id': 'KS-2',
                },
                format='json',
            )
            self.assertEqual(blocked.status_code, 403)
            self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
            reject_url = reverse(
                'web_wallet_funding:funding-request-reject',
                kwargs={'public_id': public_id},
            )
            rejected = self.client.post(reject_url, {'reason': 'no'}, format='json')
            self.assertEqual(rejected.status_code, 200)
            self.assertEqual(rejected.data['status'], 'failed')

    def test_customer_history_omits_reviewer(self):
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'HIST-1',
            },
            format='json',
        )
        public_id = response.data['transaction']['public_id']
        txn = WalletTransaction.objects.get(public_id=public_id)
        approve_recharge(txn, reviewed_by=self.admin)
        detail = self.client.get(
            reverse('wallet:wallet-transaction-detail', kwargs={'public_id': public_id})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('reviewed_by', detail.data)
        self.assertNotIn('reviewed_by_email', detail.data)
        self.assertIn('reviewed_at', detail.data)

    def test_invalid_method_and_blank_trx(self):
        bad_method = self.client.post(
            self.recharge_url,
            {'amount': '10.00', 'payment_method': 'manual', 'transaction_id': 'X'},
            format='json',
        )
        self.assertEqual(bad_method.status_code, 400)
        blank = self.client.post(
            self.recharge_url,
            {'amount': '10.00', 'payment_method': 'bkash', 'transaction_id': '  '},
            format='json',
        )
        self.assertEqual(blank.status_code, 400)


class ConcurrentFundingTests(TransactionTestCase):
    def setUp(self):
        self.user, self.profile = _make_customer(username='conc1', phone='1710000001')
        get_or_create_wallet(self.profile)

    def test_duplicate_provider_ref_integrity_path(self):
        request_recharge(
            self.profile,
            Decimal('5.00'),
            payment_method='bkash',
            transaction_id='CONC-TX',
        )
        with self.assertRaises(DuplicateProviderRefError):
            request_recharge(
                self.profile,
                Decimal('5.00'),
                payment_method='bkash',
                transaction_id='CONC-TX',
            )
        self.assertEqual(
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.RECHARGE,
                method='bkash',
                external_ref='CONC-TX',
            ).count(),
            1,
        )
