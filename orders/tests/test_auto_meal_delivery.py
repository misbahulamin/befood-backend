from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.authtoken.models import Token

from meals.models import MealCategory
from orders.models import OrderDelivery, OrderWalletSettings
from orders.services.auto_meal_delivery import (
    eligible_delivery_queryset,
    run_auto_delivery,
)
from orders.services.meal_off import customer_meal_off
from orders.services.order_delivery import mark_delivery_and_notify
from orders.services.order_service import create_meal_order
from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot
from user_management.models import AdminProfile, CustomerProfile, DeviceToken
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AUTO_MEAL_DELIVERY_ENABLED=True,
    MEAL_DELIVERY_WALLET_CHARGE_ENABLED=True,
)
class AutoMealDeliveryTests(TestCase):
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
            username='auto_del_customer',
            email='auto_del_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712222101',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

        self.customer_user_b = User.objects.create_user(
            username='auto_del_customer_b',
            email='auto_del_customer_b@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user_b.groups.add(customer_group)
        self.customer_profile_b = CustomerProfile.objects.create(
            user=self.customer_user_b,
            phone='1712222102',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

        self.admin_user = User.objects.create_user(
            username='auto_del_admin',
            email='auto_del_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        Token.objects.create(user=self.admin_user)

        self.daily_lunch = MealCategory.objects.create(
            meal_name='Auto Lunch Pack',
            total_price=Decimal('65.00'),
            meal_thumbnail=make_test_image('auto_lunch.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        self.daily_both = MealCategory.objects.create(
            meal_name='Auto Both Pack',
            total_price=Decimal('130.00'),
            meal_thumbnail=make_test_image('auto_both.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
        )

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('0.00')
        settings_obj.save()

        self.wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(self.wallet, Decimal('500.00'))
        self.wallet_b = get_or_create_wallet(self.customer_profile_b)
        credit_wallet(self.wallet_b, Decimal('500.00'))
        self.service_date = date(2026, 8, 5)
        self.slot_price = Decimal('62.00')

    def _order_lunch(self, profile):
        with patch(
            'orders.services.order_duration.timezone.localdate',
            return_value=self.service_date,
        ):
            order = create_meal_order(profile, self.daily_lunch)
        delivery = order.deliveries.get()
        ensure_priced_delivery_slot(
            order.meal,
            delivery.service_date,
            delivery.meal_period,
            price=self.slot_price,
        )
        return order, delivery

    def _order_both(self, profile):
        with patch(
            'orders.services.order_duration.timezone.localdate',
            return_value=self.service_date,
        ):
            order = create_meal_order(profile, self.daily_both)
        for delivery in order.deliveries.all():
            ensure_priced_delivery_slot(
                order.meal,
                delivery.service_date,
                delivery.meal_period,
                price=self.slot_price if delivery.meal_period == 'lunch' else Decimal('38.00'),
            )
        lunch = order.deliveries.get(meal_period=OrderDelivery.MealPeriod.LUNCH)
        dinner = order.deliveries.get(meal_period=OrderDelivery.MealPeriod.DINNER)
        return order, lunch, dinner

    def test_meal_off_excluded_from_candidates(self):
        _order, delivery = self._order_lunch(self.customer_profile)
        now = datetime(2026, 8, 4, 12, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        with patch('orders.services.meal_off.meal_off_business_now', return_value=now):
            customer_meal_off(delivery, self.customer_user)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SKIPPED)

        qs = eligible_delivery_queryset(self.service_date, OrderDelivery.MealPeriod.LUNCH)
        self.assertFalse(qs.filter(pk=delivery.pk).exists())

    def test_scheduled_live_included_and_charged(self):
        _order, delivery = self._order_lunch(self.customer_profile)
        balance_before = self.wallet.balance

        with patch(
            'notifications.services.meal_delivery_notifications.send_to_tokens',
            return_value=[],
        ):
            result = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )

        delivery.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.delivered, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(delivery.payment_status, OrderDelivery.PaymentStatus.CHARGED)
        self.assertEqual(self.wallet.balance, balance_before - self.slot_price)
        self.assertIn('Auto-delivered by cron', delivery.note or '')

    def test_insufficient_wallet_isolates_failure(self):
        _a, delivery_a = self._order_lunch(self.customer_profile)
        _b, delivery_b = self._order_lunch(self.customer_profile_b)

        # Drain wallet A below slot price.
        self.wallet.refresh_from_db()
        from wallet.services.ledger import debit_wallet

        if self.wallet.balance > Decimal('10.00'):
            debit_wallet(
                self.wallet,
                self.wallet.balance - Decimal('10.00'),
                type='adjustment',
                note='drain for test',
            )

        with patch(
            'notifications.services.meal_delivery_notifications.send_to_tokens',
            return_value=[],
        ):
            result = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )

        delivery_a.refresh_from_db()
        delivery_b.refresh_from_db()
        self.assertEqual(result.candidate_count, 2)
        self.assertEqual(result.delivered, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(delivery_a.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertEqual(delivery_b.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertTrue(
            any(f.code == 'WALLET_INSUFFICIENT_FOR_MEAL' for f in result.failures)
        )

    def test_dry_run_mutates_nothing(self):
        _order, delivery = self._order_lunch(self.customer_profile)
        balance_before = self.wallet.balance

        result = run_auto_delivery(
            service_date=self.service_date,
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            dry_run=True,
            acquire_lock=False,
        )

        delivery.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.delivered, 0)
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertEqual(self.wallet.balance, balance_before)

    def test_lunch_job_ignores_dinner(self):
        _order, lunch, dinner = self._order_both(self.customer_profile)

        with patch(
            'notifications.services.meal_delivery_notifications.send_to_tokens',
            return_value=[],
        ):
            result = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )

        lunch.refresh_from_db()
        dinner.refresh_from_db()
        self.assertEqual(result.delivered, 1)
        self.assertEqual(lunch.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(dinner.status, OrderDelivery.DeliveryStatus.SCHEDULED)

    def test_idempotent_second_run(self):
        _order, delivery = self._order_lunch(self.customer_profile)
        with patch(
            'notifications.services.meal_delivery_notifications.send_to_tokens',
            return_value=[],
        ):
            first = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )
            second = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )

        self.assertEqual(first.delivered, 1)
        self.assertEqual(second.candidate_count, 0)
        self.assertEqual(second.delivered, 0)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(
            delivery.wallet_transaction.amount,
            self.slot_price,
        )

    @patch('notifications.services.meal_delivery_notifications.send_to_tokens')
    def test_notify_on_deliver_not_on_skip(self, mock_send):
        mock_send.return_value = []
        DeviceToken.objects.create(
            user=self.customer_user,
            token='fcm-auto-test-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )
        _order, delivery = self._order_lunch(self.customer_profile)

        mark_delivery_and_notify(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(mock_send.call_count, 1)
        _tokens, title, body, data = mock_send.call_args[0]
        self.assertEqual(title, 'Meal delivered')
        self.assertEqual(data['type'], 'meal_delivered')
        self.assertEqual(data['screen'], 'my_meal')
        self.assertEqual(data['entity_type'], 'delivery')
        self.assertEqual(data['entity_id'], str(delivery.public_id))
        self.assertEqual(data['delivery_public_id'], str(delivery.public_id))

        _order2, delivery2 = self._order_lunch(self.customer_profile_b)
        ensure_priced_delivery_slot(
            delivery2.order.meal,
            delivery2.service_date,
            delivery2.meal_period,
            price=self.slot_price,
        )
        mock_send.reset_mock()
        mark_delivery_and_notify(delivery2, 'skipped', marked_by=self.admin_user)
        mock_send.assert_not_called()

    @patch('notifications.services.meal_delivery_notifications.send_to_tokens')
    def test_notify_failure_keeps_delivered(self, mock_send):
        mock_send.side_effect = RuntimeError('FCM down')
        DeviceToken.objects.create(
            user=self.customer_user,
            token='fcm-auto-fail-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )
        _order, delivery = self._order_lunch(self.customer_profile)
        balance_before = self.wallet.balance

        updated = mark_delivery_and_notify(delivery, 'delivered', marked_by=self.admin_user)
        updated.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(updated.status, OrderDelivery.DeliveryStatus.DELIVERED)
        self.assertEqual(updated.payment_status, OrderDelivery.PaymentStatus.CHARGED)
        self.assertEqual(self.wallet.balance, balance_before - self.slot_price)

    def test_management_command_dry_run(self):
        self._order_lunch(self.customer_profile)
        call_command(
            'auto_deliver_meals',
            meal_period='lunch',
            date='2026-08-05',
            dry_run=True,
            no_lock=True,
        )
        self.assertEqual(
            OrderDelivery.objects.filter(
                status=OrderDelivery.DeliveryStatus.SCHEDULED,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
            ).count(),
            1,
        )

    def test_disabled_setting_noops(self):
        self._order_lunch(self.customer_profile)
        with override_settings(AUTO_MEAL_DELIVERY_ENABLED=False):
            result = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )
        self.assertTrue(result.disabled)
        self.assertEqual(result.delivered, 0)
