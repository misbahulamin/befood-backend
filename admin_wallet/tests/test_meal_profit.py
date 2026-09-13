"""Tests for immutable meal profit ledger and Admin Profit APIs."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.models import MealProfitTransaction
from admin_wallet.services.profit_analytics import dashboard_payload
from admin_wallet.services.profit_ledger import recognize_meal_profit
from meals.models import MealCategory, MealCycle, MealCyclePlan, MonthlyMenuSchedule, MonthlyMenuSlot
from orders.models import OrderDelivery, OrderWalletSettings
from orders.services.meal_off import customer_meal_off
from orders.services.order_delivery import DeliveryError, mark_delivery
from orders.services.order_service import create_meal_order
from user_management.models import AdminProfile, CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def ensure_priced_delivery_slot(
    meal,
    service_date,
    meal_period,
    price=Decimal('62.00'),
    *,
    profit=Decimal('2.00'),
    food_cost=Decimal('20.00'),
):
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
            'ingredient_cost_snapshot': food_cost,
            'operational_cost_snapshot': Decimal('31.00'),
            'profit_snapshot': profit,
        },
    )
    return slot


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEAL_DELIVERY_WALLET_CHARGE_ENABLED=True,
)
class MealProfitTrackingTests(APITestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        Group.objects.get_or_create(name='ADMIN')
        Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='profit_admin',
            email='profit_admin@example.com',
            password='StrongPassword123',
            is_staff=True,
            is_active=True,
        )
        self.admin_user.groups.add(Group.objects.get(name='ADMIN'))
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='profit_customer',
            email='profit_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(Group.objects.get(name='CUSTOMER'))
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1713333088',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.daily_meal = MealCategory.objects.create(
            meal_name='Profit Student Package',
            total_price=Decimal('65.00'),
            meal_thumbnail=make_test_image('profit-pkg.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.meal_stop_threshold = Decimal('0.00')
        settings_obj.save()

        self.wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(self.wallet, Decimal('500.00'))

    def _charge_delivery(self, *, profit=Decimal('3.10'), price=Decimal('62.00')):
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        ensure_priced_delivery_slot(
            delivery.order.meal,
            delivery.service_date,
            delivery.meal_period,
            price=price,
            profit=profit,
            food_cost=Decimal('28.00'),
        )
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        delivery.refresh_from_db()
        return delivery

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_successful_delivery_creates_profit_record(self, _mock_date):
        delivery = self._charge_delivery(profit=Decimal('3.10'))
        self.assertEqual(delivery.payment_status, OrderDelivery.PaymentStatus.CHARGED)
        row = MealProfitTransaction.objects.get(order_delivery=delivery)
        self.assertEqual(row.profit_amount, Decimal('3.10'))
        self.assertEqual(row.meal_price, Decimal('62.00'))
        self.assertEqual(row.food_cost, Decimal('28.00'))
        self.assertEqual(row.source, MealProfitTransaction.Source.MANUAL_DELIVERY)
        self.assertEqual(row.customer_id, self.customer_profile.id)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_retry_does_not_duplicate_profit(self, _mock_date):
        delivery = self._charge_delivery(profit=Decimal('3.10'))
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(MealProfitTransaction.objects.filter(order_delivery=delivery).count(), 1)
        again = recognize_meal_profit(delivery)
        self.assertEqual(MealProfitTransaction.objects.filter(order_delivery=delivery).count(), 1)
        self.assertEqual(again.pk, MealProfitTransaction.objects.get(order_delivery=delivery).pk)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_meal_off_does_not_create_profit(self, _mock_date):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        ensure_priced_delivery_slot(
            delivery.order.meal,
            delivery.service_date,
            delivery.meal_period,
            profit=Decimal('3.10'),
        )
        # Before meal-off cutoff on the service date.
        now = datetime(2026, 8, 5, 0, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        with patch('orders.services.meal_off.meal_off_business_now', return_value=now):
            customer_meal_off(delivery, self.customer_user)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertFalse(MealProfitTransaction.objects.filter(order_delivery=delivery).exists())

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_insufficient_balance_does_not_create_profit(self, _mock_date):
        self.wallet.balance = Decimal('1.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        order = create_meal_order(self.customer_profile, self.daily_meal)
        delivery = order.deliveries.get()
        ensure_priced_delivery_slot(
            delivery.order.meal,
            delivery.service_date,
            delivery.meal_period,
            price=Decimal('62.00'),
            profit=Decimal('3.10'),
        )
        with patch('orders.services.order_delivery.timezone.localdate', return_value=date(2026, 8, 5)):
            with self.assertRaises(DeliveryError):
                mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        delivery.refresh_from_db()
        self.assertNotEqual(delivery.payment_status, OrderDelivery.PaymentStatus.CHARGED)
        self.assertFalse(MealProfitTransaction.objects.filter(order_delivery=delivery).exists())

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_admin_profit_dashboard_and_history(self, _mock_date):
        delivery = self._charge_delivery(profit=Decimal('3.10'))
        payload = dashboard_payload(
            start_date=delivery.service_date,
            end_date=delivery.service_date,
        )
        self.assertEqual(payload['lifetime_profit'], Decimal('3.10'))
        self.assertEqual(payload['range_profit'], Decimal('3.10'))
        self.assertEqual(len(payload['profit_by_package']), 1)
        self.assertEqual(payload['profit_by_package'][0]['profit'], Decimal('3.10'))
        self.assertTrue(any(r['meal_period'] == delivery.meal_period for r in payload['profit_by_meal_period']))
        self.assertEqual(payload['profit_by_customer'][0]['profit'], Decimal('3.10'))
        self.assertTrue(payload['daily_profit_chart'])

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        dash = self.client.get(reverse('web_admin_profit:dashboard'))
        self.assertEqual(dash.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(dash.data['lifetime_profit']), Decimal('3.10'))

        history = self.client.get(
            reverse('web_admin_profit:history'),
            {
                'start_date': delivery.service_date.isoformat(),
                'end_date': delivery.service_date.isoformat(),
                'package': str(self.daily_meal.public_id),
                'customer': str(self.customer_profile.public_id),
                'meal_period': delivery.meal_period,
            },
        )
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(len(history.data['results']), 1)
        self.assertEqual(Decimal(history.data['results'][0]['profit_amount']), Decimal('3.10'))

        bad = self.client.get(reverse('web_admin_profit:history'), {'unknown': 'x'})
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        range_dash = self.client.get(
            reverse('web_admin_profit:dashboard'),
            {
                'start_date': '2026-08-01',
                'end_date': '2026-08-31',
            },
        )
        self.assertEqual(range_dash.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(range_dash.data['range_profit']), Decimal('3.10'))

    def test_admin_profit_permissions(self):
        url = reverse('web_admin_profit:dashboard')
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        denied = self.client.get(url)
        self.assertIn(denied.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_backfill_idempotent_and_dry_run(self, _mock_date):
        delivery = self._charge_delivery(profit=Decimal('3.10'))
        MealProfitTransaction.objects.filter(order_delivery=delivery).delete()
        self.assertEqual(MealProfitTransaction.objects.count(), 0)

        call_command('backfill_meal_profit', dry_run=True)
        self.assertEqual(MealProfitTransaction.objects.count(), 0)

        call_command('backfill_meal_profit')
        self.assertEqual(MealProfitTransaction.objects.count(), 1)
        row = MealProfitTransaction.objects.get(order_delivery=delivery)
        self.assertEqual(row.source, MealProfitTransaction.Source.BACKFILL)
        self.assertEqual(row.profit_amount, Decimal('3.10'))

        call_command('backfill_meal_profit', validate=True)
        self.assertEqual(MealProfitTransaction.objects.count(), 1)

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 8, 5))
    def test_snapshot_immutable_after_catalog_change(self, _mock_date):
        delivery = self._charge_delivery(profit=Decimal('3.10'))
        row = MealProfitTransaction.objects.get(order_delivery=delivery)
        slot = MonthlyMenuSlot.objects.get(
            service_date=delivery.service_date,
            meal_period=delivery.meal_period,
            schedule__plan__meal_category=delivery.order.meal,
        )
        slot.profit_snapshot = Decimal('99.00')
        slot.ingredient_cost_snapshot = Decimal('1.00')
        slot.save()
        row.refresh_from_db()
        self.assertEqual(row.profit_amount, Decimal('3.10'))
        self.assertEqual(row.food_cost, Decimal('28.00'))
