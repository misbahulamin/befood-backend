from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.models import AdminWalletAuditLog, AdminWalletTransaction
from admin_wallet.services.ledger import (
    InsufficientFundsError,
    credit_admin_wallet,
    debit_admin_wallet,
    get_or_create_platform_wallet,
)
from admin_wallet.services.operations import manual_deposit, post_expense, withdraw
from admin_wallet.services.queries import reconcile_balance
from meals.models import MealCategory, MealCycle, MealCyclePlan, MonthlyMenuSchedule, MonthlyMenuSlot
from orders.models import OrderDelivery, OrderWalletSettings
from orders.services.order_delivery import DeliveryError, mark_delivery
from orders.services.order_service import create_meal_order
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import WalletTransaction
from wallet.services.ledger import (
    PlatformFloatError,
    credit_wallet,
    debit_wallet,
    get_or_create_wallet,
    recharge_wallet,
    withdraw_wallet,
)


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def ensure_priced_delivery_slot(meal, service_date, meal_period, price=Decimal('62.00')):
    from django.utils import timezone

    cycle, _ = MealCycle.objects.get_or_create(year=service_date.year, month=service_date.month)
    plan, created = MealCyclePlan.objects.get_or_create(
        cycle=cycle,
        meal_category=meal,
        defaults={
            'status': MealCyclePlan.Status.FINALIZED,
            'finalized_at': timezone.now(),
            'snapshot_total_cost': Decimal('50.00'),
            'snapshot_per_meal_rate': Decimal('50.00'),
        },
    )
    if not created and plan.status != MealCyclePlan.Status.FINALIZED:
        plan.status = MealCyclePlan.Status.FINALIZED
        plan.finalized_at = timezone.now()
        plan.snapshot_total_cost = Decimal('50.00')
        plan.snapshot_per_meal_rate = Decimal('50.00')
        plan.save()
    schedule, _ = MonthlyMenuSchedule.objects.get_or_create(
        plan=plan,
        defaults={
            'status': MonthlyMenuSchedule.Status.PUBLISHED,
            'published_at': timezone.now(),
        },
    )
    if schedule.status != MonthlyMenuSchedule.Status.PUBLISHED:
        schedule.status = MonthlyMenuSchedule.Status.PUBLISHED
        schedule.published_at = timezone.now()
        schedule.save(update_fields=['status', 'published_at', 'updated_at'])
    slot, _ = MonthlyMenuSlot.objects.update_or_create(
        schedule=schedule,
        service_date=service_date,
        meal_period=meal_period,
        defaults={
            'final_meal_price_snapshot': price,
            'ingredient_cost_snapshot': Decimal('20.00'),
            'operational_cost_snapshot': Decimal('31.00'),
            'profit_snapshot': Decimal('2.00'),
        },
    )
    return slot


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED=False,
    ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED=True,
)
class AdminWalletServiceTests(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='aw_admin',
            email='aw_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(Group.objects.get(name='ADMIN'))
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_verified=True)

    def test_credit_debit_and_reconcile(self):
        credit_admin_wallet(
            Decimal('100.00'),
            type=AdminWalletTransaction.Type.OTHER_INCOME,
            source='Test',
        )
        debit_admin_wallet(
            Decimal('40.00'),
            type=AdminWalletTransaction.Type.PLATFORM_EXPENSE,
            reason='ops',
            source='Test',
        )
        wallet = get_or_create_platform_wallet()
        self.assertEqual(wallet.balance, Decimal('60.00'))
        result = reconcile_balance(wallet)
        self.assertTrue(result['matches'])

    def test_overdraft_rejected(self):
        with self.assertRaises(InsufficientFundsError):
            debit_admin_wallet(
                Decimal('10.00'),
                type=AdminWalletTransaction.Type.WITHDRAWAL,
                reason='too much',
            )

    def test_idempotent_credit_replay(self):
        t1 = credit_admin_wallet(
            Decimal('25.00'),
            type=AdminWalletTransaction.Type.OTHER_INCOME,
            idempotency_key='idem-1',
        )
        t2 = credit_admin_wallet(
            Decimal('25.00'),
            type=AdminWalletTransaction.Type.OTHER_INCOME,
            idempotency_key='idem-1',
        )
        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(get_or_create_platform_wallet().balance, Decimal('25.00'))

    def test_manual_deposit_withdraw_expense_audit(self):
        deposit = manual_deposit(
            Decimal('1000.00'),
            reason='Seed capital',
            actor_admin=self.admin_profile,
        )
        self.assertEqual(deposit.type, AdminWalletTransaction.Type.MANUAL_DEPOSIT)
        self.assertTrue(
            AdminWalletAuditLog.objects.filter(
                transaction=deposit,
                action=AdminWalletAuditLog.Action.MANUAL_DEPOSIT,
            ).exists()
        )
        w = withdraw(
            Decimal('200.00'),
            reason='Operational Expense',
            actor_admin=self.admin_profile,
        )
        self.assertEqual(w.type, AdminWalletTransaction.Type.WITHDRAWAL)
        with self.assertRaises(InsufficientFundsError):
            withdraw(Decimal('99999.00'), reason='too much', actor_admin=self.admin_profile)
        exp = post_expense(
            Decimal('100.00'),
            type=AdminWalletTransaction.Type.RIDER_PAYMENT,
            reason='Rider settlement',
            actor_admin=self.admin_profile,
        )
        self.assertEqual(exp.type, AdminWalletTransaction.Type.RIDER_PAYMENT)
        wallet = get_or_create_platform_wallet()
        self.assertEqual(wallet.balance, Decimal('700.00'))


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED=False,
    ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED=True,
    MEAL_DELIVERY_WALLET_CHARGE_ENABLED=True,
)
class AdminWalletIngestionTests(APITestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.customer_user = User.objects.create_user(
            username='aw_customer',
            email='aw_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1713333001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

        self.admin_user = User.objects.create_user(
            username='aw_pay_admin',
            email='aw_pay_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)

        self.daily_meal = MealCategory.objects.create(
            meal_name='Admin Wallet Test Package',
            total_price=Decimal('65.00'),
            meal_thumbnail=make_test_image('aw-pkg.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()

        self.wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(self.wallet, Decimal('500.00'))
        self.slot_charge_price = Decimal('62.00')

    def _prepare_chargeable(self, delivery, price=None):
        ensure_priced_delivery_slot(
            delivery.order.meal,
            delivery.service_date,
            delivery.meal_period,
            price=price or self.slot_charge_price,
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_meal_charge_does_not_cash_credit_admin_wallet(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)
        before = get_or_create_platform_wallet().balance

        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)

        wallet = get_or_create_platform_wallet()
        self.assertEqual(wallet.balance, before)
        self.assertFalse(
            AdminWalletTransaction.objects.filter(
                type=AdminWalletTransaction.Type.CUSTOMER_PAYMENT,
                order_delivery=delivery,
            ).exists()
        )
        delivery.refresh_from_db()
        self.assertEqual(delivery.payment_status, OrderDelivery.PaymentStatus.CHARGED)

        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, before)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_recharge_then_meal_does_not_double_count_cash(self, _mock_date):
        AdminWalletTransaction.objects.all().delete()
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('0.00')
        platform.total_received = Decimal('0.00')
        platform.total_customer_funding = Decimal('0.00')
        platform.save()

        recharge_wallet(self.customer_profile, Decimal('200.00'), note='fund')
        after_funding = get_or_create_platform_wallet().balance
        self.assertEqual(after_funding, Decimal('200.00'))

        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)

        platform.refresh_from_db()
        self.assertEqual(platform.balance, Decimal('200.00'))
        self.assertFalse(
            AdminWalletTransaction.objects.filter(
                type=AdminWalletTransaction.Type.CUSTOMER_PAYMENT,
            ).exists()
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_failed_charge_does_not_credit_admin_wallet(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)
        self.wallet.refresh_from_db()
        if self.wallet.balance > 0:
            debit_wallet(
                self.wallet,
                self.wallet.balance,
                type=WalletTransaction.Type.ADJUSTMENT,
            )
        before = get_or_create_platform_wallet().balance
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            with self.assertRaises(DeliveryError):
                mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(get_or_create_platform_wallet().balance, before)
        self.assertFalse(
            AdminWalletTransaction.objects.filter(order_delivery=delivery).exists()
        )

    def test_customer_recharge_credits_admin_wallet(self):
        before = get_or_create_platform_wallet().balance
        AdminWalletTransaction.objects.filter(
            type=AdminWalletTransaction.Type.CUSTOMER_FUNDING,
        ).delete()
        _, txn = recharge_wallet(self.customer_profile, Decimal('50.00'), note='topup')
        platform = get_or_create_platform_wallet()
        self.assertEqual(platform.balance, before + Decimal('50.00'))
        credit = AdminWalletTransaction.objects.get(
            type=AdminWalletTransaction.Type.CUSTOMER_FUNDING,
            customer_wallet_transaction=txn,
        )
        self.assertEqual(credit.amount, Decimal('50.00'))
        self.assertEqual(credit.direction, AdminWalletTransaction.Direction.CREDIT)

    def test_customer_recharge_idempotent_admin_credit(self):
        _, txn = recharge_wallet(
            self.customer_profile,
            Decimal('40.00'),
            note='once',
            idempotency_key='aw-recharge-idem-1',
        )
        before = get_or_create_platform_wallet().balance
        recharge_wallet(
            self.customer_profile,
            Decimal('40.00'),
            note='once',
            idempotency_key='aw-recharge-idem-1',
        )
        self.assertEqual(get_or_create_platform_wallet().balance, before)
        self.assertEqual(
            AdminWalletTransaction.objects.filter(
                type=AdminWalletTransaction.Type.CUSTOMER_FUNDING,
                customer_wallet_transaction=txn,
            ).count(),
            1,
        )

    def test_customer_withdraw_debits_admin_wallet(self):
        recharge_wallet(self.customer_profile, Decimal('80.00'))
        before = get_or_create_platform_wallet().balance
        _, txn = withdraw_wallet(self.customer_profile, Decimal('30.00'))
        platform = get_or_create_platform_wallet()
        self.assertEqual(platform.balance, before - Decimal('30.00'))
        debit = AdminWalletTransaction.objects.get(
            type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
            customer_wallet_transaction=txn,
        )
        self.assertEqual(debit.amount, Decimal('30.00'))

    def test_insufficient_admin_float_blocks_customer_withdraw(self):
        # Bypass custody: customer has balance, Admin Wallet empty.
        credit_wallet(self.wallet, Decimal('25.00'))
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('0.00')
        platform.save(update_fields=['balance', 'updated_at'])
        customer_before = get_or_create_wallet(self.customer_profile).balance
        withdraw_count = AdminWalletTransaction.objects.filter(
            type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
        ).count()
        with self.assertRaises(PlatformFloatError):
            withdraw_wallet(self.customer_profile, Decimal('10.00'))
        self.assertEqual(
            get_or_create_wallet(self.customer_profile).balance,
            customer_before,
        )
        self.assertEqual(
            AdminWalletTransaction.objects.filter(
                type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
            ).count(),
            withdraw_count,
        )


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AdminWalletAPITests(APITestCase):
    def setUp(self):
        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.admin_user = User.objects.create_user(
            username='aw_api_admin',
            email='aw_api_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='aw_api_customer',
            email='aw_api_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1713333002',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

    def test_permissions(self):
        url = reverse('web_admin_wallet:summary')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        res = self.client.get(url)
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('balance', res.data)
        self.assertIn('total_customer_funding', res.data)
        self.assertIn('total_customer_withdrawals', res.data)

    def test_dashboard_deposit_filter_search(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        dep = self.client.post(
            reverse('web_admin_wallet:deposits'),
            {'amount': '1500.00', 'reason': 'Capital inject'},
            format='json',
        )
        self.assertEqual(dep.status_code, status.HTTP_201_CREATED)

        dash = self.client.get(reverse('web_admin_wallet:dashboard'))
        self.assertEqual(dash.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(dash.data['wallet']['balance']), Decimal('1500.00'))
        self.assertIn('today_income', dash.data)
        self.assertIn('total_customer_funding', dash.data)
        self.assertIn('total_customer_withdrawals', dash.data)

        listed = self.client.get(
            reverse('web_admin_wallet:transactions'),
            {'type': 'manual_deposit', 'direction': 'credit'},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(listed.data['results']), 1)

        bad = self.client.get(
            reverse('web_admin_wallet:transactions'),
            {'unknown_filter': 'x'},
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        q = self.client.get(
            reverse('web_admin_wallet:transactions'),
            {'q': str(dep.data['public_id'])},
        )
        self.assertEqual(q.status_code, status.HTTP_200_OK)
        self.assertEqual(len(q.data['results']), 1)
