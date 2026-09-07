from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.services.ledger import get_or_create_platform_wallet
from orders.models import OrderWalletSettings
from orders.services.wallet_balance_thresholds import apply_meal_service_block
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import WalletTransaction
from wallet.services.funding import (
    approve_recharge,
    approve_withdraw,
    reject_recharge,
    request_recharge,
    request_withdraw,
)
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def _make_customer(username='resume_cust', phone='1712345001'):
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


def _make_admin(username='resume_admin'):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        is_active=True,
    )
    group, _ = Group.objects.get_or_create(name='ADMIN')
    user.groups.add(group)
    AdminProfile.objects.create(user=user, is_verified=True)
    return user


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ApproveRechargeMealResumeTests(TestCase):
    def setUp(self):
        self.user, self.profile = _make_customer()
        self.admin = _make_admin()
        self.wallet = get_or_create_wallet(self.profile)
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('10000.00')
        platform.save(update_fields=['balance', 'updated_at'])

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('500.00')
        settings_obj.low_balance_reminder_threshold = Decimal('300.00')
        settings_obj.meal_stop_threshold = Decimal('150.00')
        settings_obj.save()

    def _pending_recharge(self, amount: Decimal, trx_id: str):
        _, txn, _ = request_recharge(
            self.profile,
            amount,
            payment_method='bkash',
            transaction_id=trx_id,
        )
        return txn

    def test_blocked_sufficient_recharge_clears_block(self):
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        apply_meal_service_block(self.profile)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.meal_service_blocked_low_balance)

        txn = self._pending_recharge(Decimal('100.00'), 'RESUME-OK-1')
        with mock.patch(
            'wallet.services.funding_customer_notifications.notify_customer_recharge_approved'
        ) as notify_approved:
            with self.captureOnCommitCallbacks(execute=True):
                result = approve_recharge(txn, reviewed_by=self.admin)

        self.wallet.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('200.00'))
        self.assertFalse(self.profile.meal_service_blocked_low_balance)
        self.assertIsNone(self.profile.meal_service_blocked_at)
        self.assertTrue(result.meal_service_restored)
        # Recharge-approved path may still schedule; no dedicated restore notifier.
        self.assertTrue(notify_approved.called)

    def test_blocked_insufficient_recharge_keeps_block(self):
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        apply_meal_service_block(self.profile)

        txn = self._pending_recharge(Decimal('20.00'), 'RESUME-LOW-1')
        result = approve_recharge(txn, reviewed_by=self.admin)

        self.wallet.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('120.00'))
        self.assertTrue(self.profile.meal_service_blocked_low_balance)
        self.assertFalse(result.meal_service_restored)

    def test_unblocked_recharge_leaves_flags(self):
        self.wallet.balance = Decimal('200.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        self.assertFalse(self.profile.meal_service_blocked_low_balance)

        txn = self._pending_recharge(Decimal('50.00'), 'RESUME-OPEN-1')
        result = approve_recharge(txn, reviewed_by=self.admin)

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.meal_service_blocked_low_balance)
        self.assertFalse(result.meal_service_restored)

    def test_latest_threshold_used_at_approve(self):
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        apply_meal_service_block(self.profile)

        settings_obj = OrderWalletSettings.load()
        settings_obj.meal_stop_threshold = Decimal('200.00')
        settings_obj.save(update_fields=['meal_stop_threshold', 'updated_at'])

        txn = self._pending_recharge(Decimal('80.00'), 'RESUME-THR-1')
        result = approve_recharge(txn, reviewed_by=self.admin)

        self.wallet.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('180.00'))
        self.assertTrue(self.profile.meal_service_blocked_low_balance)
        self.assertFalse(result.meal_service_restored)

    def test_pending_and_reject_do_not_resume(self):
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        apply_meal_service_block(self.profile)

        txn = self._pending_recharge(Decimal('200.00'), 'RESUME-PEND-1')
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.meal_service_blocked_low_balance)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100.00'))

        reject_recharge(txn, reviewed_by=self.admin, reason='bad')
        self.profile.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertTrue(self.profile.meal_service_blocked_low_balance)
        self.assertEqual(self.wallet.balance, Decimal('100.00'))

    def test_withdraw_approve_does_not_restore(self):
        credit_wallet(self.wallet, Decimal('300.00'))
        apply_meal_service_block(self.profile)
        _, txn, _ = request_withdraw(self.profile, Decimal('10.00'))
        approve_withdraw(txn, reviewed_by=self.admin)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.meal_service_blocked_low_balance)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ApproveRechargeMealResumeAPITests(APITestCase):
    def setUp(self):
        self.user, self.profile = _make_customer(username='resume_api', phone='1712345002')
        self.admin = _make_admin(username='resume_api_admin')
        self.admin_token = Token.objects.create(user=self.admin)
        self.wallet = get_or_create_wallet(self.profile)
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('5000.00')
        platform.save(update_fields=['balance', 'updated_at'])

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('500.00')
        settings_obj.low_balance_reminder_threshold = Decimal('300.00')
        settings_obj.meal_stop_threshold = Decimal('150.00')
        settings_obj.save()

    def test_approve_response_includes_meal_service_restored(self):
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        apply_meal_service_block(self.profile)
        _, txn, _ = request_recharge(
            self.profile,
            Decimal('100.00'),
            payment_method='bkash',
            transaction_id='API-RESUME-1',
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        approve_url = reverse(
            'web_wallet_funding:funding-request-approve',
            kwargs={'public_id': str(txn.public_id)},
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(approve_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['meal_service_restored'])
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.meal_service_blocked_low_balance)

    def test_withdraw_approve_meal_service_restored_false(self):
        credit_wallet(self.wallet, Decimal('200.00'))
        _, txn, _ = request_withdraw(self.profile, Decimal('20.00'))
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        approve_url = reverse(
            'web_wallet_funding:funding-request-approve',
            kwargs={'public_id': str(txn.public_id)},
        )
        response = self.client.post(approve_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['meal_service_restored'])
