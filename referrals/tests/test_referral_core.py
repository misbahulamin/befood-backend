"""Core referral commission and wallet bucket tests."""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from admin_wallet.models import AdminWallet, AdminWalletTransaction
from admin_wallet.services.ledger import credit_admin_wallet
from meals.models import MealCategory
from orders.models import CustomerSubscription, OrderDelivery
from referrals.models import ReferralCommission, ReferralProgramSettings
from referrals.services.attribution import attribute_on_signup
from referrals.services.codes import ensure_referral_profile, generate_referral_code
from referrals.services.commission import (
    credit_referral_commission_for_delivery,
    manual_adjust_referral_commission,
    reverse_referral_commission,
)
from referrals.services.eligibility import ReferralError
from referrals.services.settings import update_referral_commission_percent
from user_management.models import CustomerProfile
from wallet.models import WalletTransaction
from wallet.services.funding import request_withdraw
from wallet.services.ledger import (
    STRATEGY_COMMISSION_FIRST,
    InsufficientFundsError,
    credit_wallet,
    debit_wallet,
    get_or_create_wallet,
)


def _thumb():
    buf = BytesIO()
    Image.new('RGB', (8, 8), color='red').save(buf, format='JPEG')
    return SimpleUploadedFile('t.jpg', buf.getvalue(), content_type='image/jpeg')


def _customer(username: str) -> CustomerProfile:
    user = User.objects.create_user(
        username=username, email=f'{username}@ex.com', password='x'
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    return CustomerProfile.objects.create(user=user)


class WalletBucketTests(TestCase):
    def test_commission_credit_and_meal_debit_order(self):
        customer = _customer('w1')
        wallet = get_or_create_wallet(customer)
        credit_wallet(wallet, Decimal('10.00'), type=WalletTransaction.Type.RECHARGE)
        credit_wallet(
            wallet,
            Decimal('3.00'),
            type=WalletTransaction.Type.REFERRAL_COMMISSION,
        )
        wallet.refresh_from_db()
        self.assertEqual(wallet.recharge_balance, Decimal('10.00'))
        self.assertEqual(wallet.commission_balance, Decimal('3.00'))
        self.assertEqual(wallet.balance, Decimal('13.00'))

        txn = debit_wallet(
            wallet,
            Decimal('5.00'),
            type=WalletTransaction.Type.PAYMENT,
            strategy=STRATEGY_COMMISSION_FIRST,
        )
        wallet.refresh_from_db()
        self.assertEqual(wallet.commission_balance, Decimal('0.00'))
        self.assertEqual(wallet.recharge_balance, Decimal('8.00'))
        self.assertEqual(txn.balance_after, Decimal('8.00'))
        self.assertEqual(
            txn.recharge_balance_after + txn.commission_balance_after,
            txn.balance_after,
        )

    def test_withdraw_blocked_when_only_commission(self):
        customer = _customer('w2')
        wallet = get_or_create_wallet(customer)
        credit_wallet(
            wallet,
            Decimal('50.00'),
            type=WalletTransaction.Type.REFERRAL_COMMISSION,
        )
        with self.assertRaises(InsufficientFundsError):
            request_withdraw(customer, Decimal('10.00'))


@override_settings(REFERRAL_ENABLED=True, REFERRAL_COMMISSION_PERCENT='5')
class ReferralCommissionTests(TestCase):
    def setUp(self):
        self.referrer = _customer('ref')
        self.referred = _customer('ree')
        ensure_referral_profile(self.referrer)
        ensure_referral_profile(self.referred)
        meal = MealCategory.objects.create(
            meal_name='Test Meal',
            total_price=Decimal('100.00'),
            meal_thumbnail=_thumb(),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
            is_subscribable=True,
        )
        for customer in (self.referrer, self.referred):
            CustomerSubscription.objects.create(
                customer=customer,
                meal=meal,
                meal_name_snapshot='Test Meal',
                meal_period_snapshot='lunch',
                status=CustomerSubscription.Status.ACTIVE,
                started_on=timezone.localdate(),
            )
        attribute_on_signup(
            referred_customer=self.referred,
            referral_code=self.referrer.referral_profile.code,
            client_type='mobile',
        )
        AdminWallet.objects.get_or_create(
            code=AdminWallet.PLATFORM_CODE,
            defaults={'balance': Decimal('0.00')},
        )
        credit_admin_wallet(
            Decimal('100.00'),
            type=AdminWalletTransaction.Type.MANUAL_DEPOSIT,
            note='test float',
        )

    def _referrer_sub(self):
        return CustomerSubscription.objects.get(customer=self.referrer)

    def _referred_sub(self):
        return CustomerSubscription.objects.get(customer=self.referred)

    def _delivery(
        self,
        customer_sub,
        *,
        amount=Decimal('100.00'),
        service_date=None,
        meal_period='lunch',
        status=OrderDelivery.DeliveryStatus.DELIVERED,
        payment_status=OrderDelivery.PaymentStatus.CHARGED,
    ):
        charged = (
            amount
            if payment_status == OrderDelivery.PaymentStatus.CHARGED
            else None
        )
        return OrderDelivery.objects.create(
            subscription=customer_sub,
            service_date=service_date or timezone.localdate(),
            meal_period=meal_period,
            status=status,
            payment_status=payment_status,
            charged_amount=charged,
        )

    def _ensure_referrer_delivered(
        self,
        *,
        service_date=None,
        meal_period='lunch',
        payment_status=OrderDelivery.PaymentStatus.NOT_APPLICABLE,
    ):
        return OrderDelivery.objects.create(
            subscription=self._referrer_sub(),
            service_date=service_date or timezone.localdate(),
            meal_period=meal_period,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            payment_status=payment_status,
            charged_amount=None,
        )

    def test_code_format(self):
        code = generate_referral_code()
        self.assertTrue(code.startswith('BEF'))
        self.assertEqual(len(code), 11)

    def test_five_percent_success(self):
        delivery = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered()
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status, ReferralCommission.Status.SUCCESS)
        self.assertEqual(row.commission_amount, Decimal('5.00'))
        wallet = get_or_create_wallet(self.referrer)
        wallet.refresh_from_db()
        self.assertEqual(wallet.commission_balance, Decimal('5.00'))

    def test_referrer_delivered_uncharged_still_qualifies(self):
        delivery = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered(
            payment_status=OrderDelivery.PaymentStatus.NOT_APPLICABLE
        )
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status, ReferralCommission.Status.SUCCESS)

    def test_referrer_meal_off_skipped(self):
        delivery = self._delivery(self._referred_sub())
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status, ReferralCommission.Status.SKIPPED)
        self.assertEqual(row.status_reason, 'REFERRER_MEAL_NOT_CONSUMED')

    def test_different_meal_period_skipped(self):
        delivery = self._delivery(self._referred_sub(), meal_period='lunch')
        self._ensure_referrer_delivered(meal_period='dinner')
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status, ReferralCommission.Status.SKIPPED)
        self.assertEqual(row.status_reason, 'REFERRER_MEAL_NOT_CONSUMED')

    def test_different_service_date_skipped(self):
        from datetime import timedelta

        today = timezone.localdate()
        delivery = self._delivery(self._referred_sub(), service_date=today)
        self._ensure_referrer_delivered(service_date=today - timedelta(days=1))
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status, ReferralCommission.Status.SKIPPED)
        self.assertEqual(row.status_reason, 'REFERRER_MEAL_NOT_CONSUMED')

    def test_referred_first_then_referrer_upgrades_same_row(self):
        from referrals.services.commission import (
            credit_pending_commissions_after_referrer_meal,
        )

        delivery = self._delivery(self._referred_sub())
        skipped = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(skipped.status, ReferralCommission.Status.SKIPPED)
        self.assertEqual(skipped.status_reason, 'REFERRER_MEAL_NOT_CONSUMED')

        referrer_delivery = self._ensure_referrer_delivered()
        results = credit_pending_commissions_after_referrer_meal(referrer_delivery)
        self.assertTrue(results)
        upgraded = results[0]
        self.assertEqual(upgraded.pk, skipped.pk)
        self.assertEqual(upgraded.status, ReferralCommission.Status.SUCCESS)
        self.assertEqual(
            ReferralCommission.objects.filter(
                order_delivery=delivery, is_manual=False, reversal_of__isnull=True
            ).count(),
            1,
        )

    def test_idempotent(self):
        delivery = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered()
        a = credit_referral_commission_for_delivery(delivery)
        b = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(a.status, ReferralCommission.Status.SUCCESS)

    def test_inactive_referrer_skipped(self):
        CustomerSubscription.objects.filter(customer=self.referrer).update(
            status=CustomerSubscription.Status.CANCELLED
        )
        delivery = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered()
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status, ReferralCommission.Status.SKIPPED)
        self.assertEqual(row.status_reason, 'REFERRER_INACTIVE')

    def test_reverse_once(self):
        delivery = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered()
        row = credit_referral_commission_for_delivery(delivery)
        reverse_referral_commission(row, reason='admin correction')
        row.refresh_from_db()
        self.assertEqual(row.status, ReferralCommission.Status.REVERSED)
        with self.assertRaises(ReferralError):
            reverse_referral_commission(row, reason='again')

    def test_manual_adjust(self):
        row = manual_adjust_referral_commission(
            referrer=self.referrer,
            amount=Decimal('10.00'),
            reason='goodwill',
        )
        self.assertTrue(row.is_manual)
        self.assertEqual(row.commission_amount, Decimal('10.00'))

    def test_reconcile_dry_run_no_writes(self):
        from django.core.management import call_command
        from io import StringIO

        delivery = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered()
        # No commission row yet; dry-run must not create one.
        out = StringIO()
        call_command('reconcile_referral_commissions', '--dry-run', '--limit', '10', stdout=out)
        self.assertFalse(
            ReferralCommission.objects.filter(order_delivery=delivery).exists()
        )
        self.assertIn('DRY-RUN', out.getvalue())
        wallet = get_or_create_wallet(self.referrer)
        wallet.refresh_from_db()
        self.assertEqual(wallet.commission_balance, Decimal('0.00'))

    def test_updated_percent_applies_to_new_accrual_only(self):
        ReferralProgramSettings.load()
        delivery_a = self._delivery(self._referred_sub())
        self._ensure_referrer_delivered()
        first = credit_referral_commission_for_delivery(delivery_a)
        self.assertEqual(first.status, ReferralCommission.Status.SUCCESS)
        self.assertEqual(first.commission_percent, Decimal('5.00'))
        self.assertEqual(first.commission_amount, Decimal('5.00'))

        update_referral_commission_percent(
            referral_commission_percent=Decimal('10.00')
        )

        first.refresh_from_db()
        self.assertEqual(first.commission_percent, Decimal('5.00'))
        self.assertEqual(first.commission_amount, Decimal('5.00'))

        from datetime import timedelta

        tomorrow = timezone.localdate() + timedelta(days=1)
        delivery_b = self._delivery(self._referred_sub(), service_date=tomorrow)
        self._ensure_referrer_delivered(service_date=tomorrow)
        second = credit_referral_commission_for_delivery(delivery_b)
        self.assertEqual(second.status, ReferralCommission.Status.SUCCESS)
        self.assertEqual(second.commission_percent, Decimal('10.00'))
        self.assertEqual(second.commission_amount, Decimal('10.00'))
        first.refresh_from_db()
        self.assertEqual(first.commission_percent, Decimal('5.00'))
        self.assertEqual(first.commission_amount, Decimal('5.00'))
