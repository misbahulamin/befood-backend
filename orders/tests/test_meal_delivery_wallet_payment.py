from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory, MealCycle, MealCyclePlan, MonthlyMenuSchedule, MonthlyMenuSlot
from orders.models import Order, OrderDelivery, OrderWalletSettings
from orders.services.meal_off import customer_meal_off
from orders.services.order_delivery import DeliveryError, close_expired_order, mark_delivery
from orders.services.order_service import create_meal_order
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import Wallet, WalletTransaction
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def ensure_priced_delivery_slot(meal, service_date, meal_period, price=Decimal('62.00')):
    """Published menu slot with final price for wallet charge tests."""
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


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MealDeliveryWalletPaymentTests(APITestCase):
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
            username='pay_customer',
            email='pay_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712222001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.admin_user = User.objects.create_user(
            username='pay_admin',
            email='pay_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.daily_meal = MealCategory.objects.create(
            meal_name='Premium Meal Package',
            total_price=Decimal('65.00'),
            meal_thumbnail=make_test_image('premium.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        self.daily_dinner = MealCategory.objects.create(
            meal_name='Dinner Package',
            total_price=Decimal('70.00'),
            meal_thumbnail=make_test_image('dinner.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.DINNER,
            is_active=True,
        )

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()

        self.wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(self.wallet, Decimal('500.00'))
        self.wallet.refresh_from_db()

        self.txn_list_url = reverse('wallet:wallet-transaction-list')
        self.slot_charge_price = Decimal('62.00')

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def _fund(self, amount=Decimal('500.00')):
        self.wallet.refresh_from_db()
        if self.wallet.balance < amount:
            credit_wallet(self.wallet, amount - self.wallet.balance)
            self.wallet.refresh_from_db()

    def _prepare_chargeable(self, delivery, price=None):
        ensure_priced_delivery_slot(
            delivery.order.meal,
            delivery.service_date,
            delivery.meal_period,
            price=price or self.slot_charge_price,
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_mark_delivered_debits_snapshot_and_creates_payment(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)
        balance_before = self.wallet.balance

        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            marked = mark_delivery(delivery, 'delivered', marked_by=self.admin_user)

        marked.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(marked.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(marked.payment_status, OrderDelivery.PaymentStatus.CHARGED)
        self.assertIsNotNone(marked.wallet_transaction_id)
        self.assertEqual(marked.charged_amount, self.slot_charge_price)
        self.assertEqual(
            self.wallet.balance,
            balance_before - self.slot_charge_price,
        )

        txn = marked.wallet_transaction
        self.assertEqual(txn.type, WalletTransaction.Type.PAYMENT)
        self.assertEqual(txn.direction, WalletTransaction.Direction.DEBIT)
        self.assertEqual(txn.amount, self.slot_charge_price)
        self.assertEqual(txn.metadata.get('purpose'), 'meal_delivery')
        self.assertEqual(txn.metadata.get('meal_period'), 'lunch')
        self.assertEqual(txn.metadata.get('service_date'), '2026-08-05')
        self.assertEqual(txn.metadata.get('meal_name'), 'Premium Meal Package')
        self.assertEqual(txn.metadata.get('delivery_public_id'), str(delivery.public_id))
        self.assertEqual(txn.metadata.get('order_public_id'), str(order.public_id))
        self.assertEqual(txn.metadata.get('final_meal_price'), '62.00')
        self.assertEqual(txn.metadata.get('charge_source'), 'slot_final_price')
        # Slot price differs from package average snapshot on the order.
        self.assertNotEqual(self.slot_charge_price, order.per_meal_price_snapshot)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    @patch('orders.services.meal_off.meal_off_business_now')
    def test_meal_off_admin_skip_and_missed_do_not_debit(self, mock_now, _mock_date):
        mock_now.return_value = datetime(2026, 8, 4, 12, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        balance_before = Wallet.objects.get(pk=self.wallet.pk).balance
        customer_meal_off(delivery, self.customer_user)
        delivery.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(delivery.payment_status, OrderDelivery.PaymentStatus.NOT_APPLICABLE)
        self.assertEqual(self.wallet.balance, balance_before)
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                type=WalletTransaction.Type.PAYMENT,
            ).count(),
            0,
        )

        Order.objects.filter(pk=order.pk).update(order_status=Order.OrderStatus.CANCELLED)
        order2 = create_meal_order(
            self.customer_profile,
            self.daily_dinner,
            year=2026,
            month=9,
        )
        skip_delivery = order2.deliveries.get()
        balance_before = Wallet.objects.get(pk=self.wallet.pk).balance
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 9, 1)):
            mark_delivery(skip_delivery, 'skipped', marked_by=self.admin_user)
        skip_delivery.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(skip_delivery.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(self.wallet.balance, balance_before)

        Order.objects.filter(pk=order2.pk).update(order_status=Order.OrderStatus.CANCELLED)
        order3 = create_meal_order(
            self.customer_profile,
            self.daily_meal,
            year=2026,
            month=10,
        )
        missed_delivery = order3.deliveries.get()
        balance_before = Wallet.objects.get(pk=self.wallet.pk).balance
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 10, 15)):
            close_expired_order(order3, reference_date=date(2026, 10, 15))
        missed_delivery.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(missed_delivery.status, OrderDelivery.DeliveryStatus.MISSED)
        self.assertEqual(self.wallet.balance, balance_before)
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                type=WalletTransaction.Type.PAYMENT,
            ).count(),
            0,
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_repeated_mark_delivered_does_not_double_charge(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
            balance_after_first = Wallet.objects.get(pk=self.wallet.pk).balance
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, balance_after_first)
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                type=WalletTransaction.Type.PAYMENT,
            ).count(),
            1,
        )

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_insufficient_and_frozen_wallet_reject_mark(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)

        self.wallet.balance = Decimal('1.00')
        self.wallet.save(update_fields=['balance'])

        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            with self.assertRaises(DeliveryError) as ctx:
                mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(ctx.exception.code, 'WALLET_INSUFFICIENT_FOR_MEAL')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertEqual(delivery.payment_status, OrderDelivery.PaymentStatus.NOT_APPLICABLE)

        self._fund(Decimal('500.00'))
        self.wallet.status = Wallet.Status.FROZEN
        self.wallet.save(update_fields=['status'])
        self._auth(self.admin_token)
        mark_url = reverse(
            'web_orders:admin-order-mark-delivery',
            kwargs={'public_id': order.public_id, 'delivery_id': delivery.public_id},
        )
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            response = self.client.post(mark_url, {'status': 'delivered'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data.get('error_code'), 'WALLET_FROZEN')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_order_create_does_not_create_payment_debit(self, _mock_date):
        payment_before = WalletTransaction.objects.filter(
            wallet=self.wallet,
            type=WalletTransaction.Type.PAYMENT,
        ).count()
        create_meal_order(self.customer_profile, self.daily_meal)
        payment_after = WalletTransaction.objects.filter(
            wallet=self.wallet,
            type=WalletTransaction.Type.PAYMENT,
        ).count()
        self.assertEqual(payment_before, payment_after)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_wallet_history_exposes_meal_payment_context(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        self._prepare_chargeable(delivery)
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)

        self._auth(self.customer_token)
        list_response = self.client.get(self.txn_list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        results = list_response.data.get('results', list_response.data)
        payment_rows = [row for row in results if row['type'] == 'payment']
        self.assertEqual(len(payment_rows), 1)
        meal_payment = payment_rows[0]['meal_payment']
        self.assertIsNotNone(meal_payment)
        self.assertEqual(meal_payment['meal_period'], 'lunch')
        self.assertEqual(meal_payment['service_date'], '2026-08-05')
        self.assertEqual(meal_payment['meal_name'], 'Premium Meal Package')
        self.assertEqual(meal_payment['order_public_id'], str(order.public_id))
        self.assertEqual(meal_payment['delivery_public_id'], str(delivery.public_id))
        self.assertEqual(meal_payment['final_meal_price'], '62.00')
        self.assertEqual(payment_rows[0]['amount'], '62.00')

        detail_url = reverse(
            'wallet:wallet-transaction-detail',
            kwargs={'public_id': payment_rows[0]['public_id']},
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['meal_payment']['meal_period'], 'lunch')

        recharge = self.client.post(
            reverse('wallet:wallet-recharge'),
            {'amount': '10.00'},
            format='json',
        )
        self.assertEqual(recharge.status_code, status.HTTP_200_OK)
        self.assertIsNone(recharge.data['transaction']['meal_payment'])

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_missing_slot_price_rejects_delivered(self, _mock_date):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            with self.assertRaises(DeliveryError) as ctx:
                mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(ctx.exception.code, 'MEAL_SLOT_PRICE_MISSING')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)