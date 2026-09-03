from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings

from admin_wallet.services.ledger import get_or_create_platform_wallet
from user_management.models import AdminProfile, CustomerProfile, DeviceToken
from wallet.models import WalletTransaction
from wallet.services.funding import (
    FundingRequestConflictError,
    approve_recharge,
    request_recharge,
)
from wallet.services.ledger import credit_wallet, get_or_create_wallet
from wallet.services.transaction_invoice import (
    META_PREVIOUS_BALANCE,
    build_invoice_context,
    ensure_invoice_for_recharge,
)


def _make_customer(username='notify_u1', phone='1712222222', verified=True):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
        first_name='Rahim',
        last_name='Khan',
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


def _make_admin(username='notify_admin'):
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
class RechargeApprovalNotificationTests(TestCase):
    def setUp(self):
        self.user, self.profile = _make_customer()
        self.admin = _make_admin()
        self.wallet = get_or_create_wallet(self.profile)
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('10000.00')
        platform.save(update_fields=['balance', 'updated_at'])
        credit_wallet(self.wallet, Decimal('500.00'))
        self.wallet.refresh_from_db()

    def _pending_recharge(self, amount='1000.00', trx='NOTIFY-TX-1'):
        _, txn, created = request_recharge(
            self.profile,
            Decimal(amount),
            payment_method='bkash',
            transaction_id=trx,
        )
        self.assertTrue(created)
        return txn

    def test_approve_assigns_invoice_and_sends_push_and_email(self):
        DeviceToken.objects.create(
            user=self.user,
            token='recharge-device-1',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )
        txn = self._pending_recharge()
        mail.outbox.clear()

        with mock.patch(
            'wallet.services.funding_customer_notifications.send_to_tokens'
        ) as send_push:
            with self.captureOnCommitCallbacks(execute=True):
                approve_recharge(txn, reviewed_by=self.admin)

        self.wallet.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1500.00'))
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)
        self.assertTrue(txn.invoice_number)
        self.assertTrue(txn.invoice_number.startswith('INV-WR-'))
        self.assertEqual(txn.metadata.get(META_PREVIOUS_BALANCE), '500.00')

        self.assertEqual(send_push.call_count, 1)
        _tokens, title, body, data = send_push.call_args[0]
        self.assertEqual(title, 'Wallet recharge approved')
        self.assertIn('৳1000.00', body)
        self.assertIn('৳1500.00', body)
        self.assertEqual(data['type'], 'wallet_recharge_approved')
        self.assertEqual(data['entity_type'], 'wallet_transaction')
        self.assertEqual(data['entity_id'], str(txn.public_id))
        self.assertEqual(data['screen'], 'wallet')
        self.assertEqual(data['amount'], '1000.00')
        self.assertEqual(data['balance'], '1500.00')
        self.assertEqual(data['invoice_number'], txn.invoice_number)

        invoice_mails = [m for m in mail.outbox if 'invoice' in m.subject.lower()]
        self.assertEqual(len(invoice_mails), 1)
        msg = invoice_mails[0]
        self.assertEqual(msg.to, [self.user.email])
        self.assertIn(txn.invoice_number, msg.subject)
        self.assertIn('1000.00', msg.body)
        self.assertIn('500.00', msg.body)
        self.assertIn('1500.00', msg.body)
        self.assertIn('bkash', msg.body.lower())
        self.assertIn('NOTIFY-TX-1', msg.body)
        self.assertIn('Rahim', msg.body)
        self.assertTrue(msg.alternatives)
        html = msg.alternatives[0][0]
        self.assertIn(txn.invoice_number, html)
        self.assertIn('Approved', html)

    def test_second_approve_does_not_resend(self):
        DeviceToken.objects.create(
            user=self.user,
            token='recharge-device-2',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )
        txn = self._pending_recharge(trx='NOTIFY-TX-2')
        mail.outbox.clear()

        with mock.patch(
            'wallet.services.funding_customer_notifications.send_to_tokens'
        ) as send_push:
            with self.captureOnCommitCallbacks(execute=True):
                approve_recharge(txn, reviewed_by=self.admin)
            txn.refresh_from_db()
            first_invoice = txn.invoice_number
            push_count = send_push.call_count
            mail_count = len([m for m in mail.outbox if 'invoice' in m.subject.lower()])

            with self.assertRaises(FundingRequestConflictError):
                with self.captureOnCommitCallbacks(execute=True):
                    approve_recharge(txn, reviewed_by=self.admin)

            txn.refresh_from_db()
            self.assertEqual(txn.invoice_number, first_invoice)
            self.assertEqual(send_push.call_count, push_count)
            self.assertEqual(
                len([m for m in mail.outbox if 'invoice' in m.subject.lower()]),
                mail_count,
            )

    def test_fcm_and_smtp_failures_keep_credit(self):
        DeviceToken.objects.create(
            user=self.user,
            token='recharge-device-3',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )
        txn = self._pending_recharge(trx='NOTIFY-TX-3')

        with mock.patch(
            'wallet.services.funding_customer_notifications.send_to_tokens',
            side_effect=RuntimeError('fcm boom'),
        ):
            with mock.patch(
                'wallet.services.funding_customer_notifications.EmailMultiAlternatives'
            ) as mail_cls:
                mail_cls.return_value.send.side_effect = RuntimeError('smtp boom')
                with self.captureOnCommitCallbacks(execute=True):
                    approve_recharge(txn, reviewed_by=self.admin)

        self.wallet.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1500.00'))
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)
        self.assertTrue(txn.invoice_number)

    def test_missing_email_and_tokens_skip_gracefully(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])
        txn = self._pending_recharge(trx='NOTIFY-TX-4')

        with mock.patch(
            'wallet.services.funding_customer_notifications.send_to_tokens'
        ) as send_push:
            with self.captureOnCommitCallbacks(execute=True):
                approve_recharge(txn, reviewed_by=self.admin)

        send_push.assert_not_called()
        self.wallet.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1500.00'))
        self.assertTrue(txn.invoice_number)
        invoice_mails = [m for m in mail.outbox if 'invoice' in m.subject.lower()]
        self.assertEqual(len(invoice_mails), 0)

    def test_invoice_context_fields(self):
        txn = self._pending_recharge(amount='250.50', trx='NOTIFY-TX-5')
        with self.captureOnCommitCallbacks(execute=True):
            approve_recharge(txn, reviewed_by=self.admin)
        txn.refresh_from_db()

        ctx = build_invoice_context(txn)
        self.assertEqual(ctx['invoice_number'], txn.invoice_number)
        self.assertEqual(ctx['amount'], '250.50')
        self.assertEqual(ctx['previous_balance'], '500.00')
        self.assertEqual(ctx['updated_balance'], '750.50')
        self.assertEqual(ctx['payment_method'], 'bkash')
        self.assertEqual(ctx['payment_reference'], 'NOTIFY-TX-5')
        self.assertEqual(ctx['customer_name'], 'Rahim Khan')
        self.assertEqual(ctx['customer_email'], self.user.email)
        self.assertEqual(ctx['customer_phone'], '+880-1712-222222')
        self.assertIn('Approved', ctx['invoice_status'])
        self.assertEqual(ctx['currency_symbol'], '৳')

        # Idempotent ensure keeps same invoice number
        ensure_invoice_for_recharge(txn, previous_balance=Decimal('500.00'))
        txn.refresh_from_db()
        self.assertEqual(txn.invoice_number, ctx['invoice_number'])
