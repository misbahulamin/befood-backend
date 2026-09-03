from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.authtoken.models import Token

from meals.models import MealCategory
from orders.models import OrderDelivery, OrderWalletSettings
from orders.services.auto_meal_delivery import eligible_delivery_queryset
from orders.services.order_delivery import mark_delivery
from orders.services.subscription_service import subscribe_customer
from orders.services.wallet_balance_thresholds import (
    apply_meal_service_block,
    run_wallet_threshold_check,
)
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
    FRONTEND_URL='https://app.example.com',
)
class WalletBalanceThresholdTests(TestCase):
    def setUp(self):
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.customer_user = User.objects.create_user(
            username='thresh_customer',
            email='thresh_customer@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712333001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

        self.admin_user = User.objects.create_user(
            username='thresh_admin',
            email='thresh_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        Token.objects.create(user=self.admin_user)

        self.plan = MealCategory.objects.create(
            meal_name='Student Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('thresh_plan.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('500.00')
        settings_obj.low_balance_reminder_threshold = Decimal('300.00')
        settings_obj.meal_stop_threshold = Decimal('200.00')
        settings_obj.save()

        self.wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(self.wallet, Decimal('700.00'))
        self.business_date = date(2026, 9, 3)

    def _subscribe(self):
        return subscribe_customer(
            self.customer_profile,
            self.plan,
            today=self.business_date,
        )

    def test_reminder_once_per_business_day(self):
        self._subscribe()
        self.wallet.balance = Decimal('298.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-reminder-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ) as send_push:
            first = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)
            second = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(first.reminded, 1)
        self.assertEqual(second.reminded, 0)
        self.customer_profile.refresh_from_db()
        self.assertEqual(self.customer_profile.last_low_balance_reminder_on, self.business_date)
        self.assertTrue(any('Low balance' in m.subject for m in mail.outbox))
        self.assertEqual(send_push.call_count, 1)
        _tokens, _title, _body, data = send_push.call_args[0]
        self.assertEqual(data['type'], 'wallet_low_balance')
        self.assertEqual(data['screen'], 'wallet')

    def test_meal_stop_blocks_auto_delivery_allows_admin_mark(self):
        subscription = self._subscribe()
        delivery = subscription.deliveries.filter(
            service_date=self.business_date,
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        ).first()
        self.assertIsNotNone(delivery)
        ensure_priced_delivery_slot(
            subscription.meal,
            delivery.service_date,
            delivery.meal_period,
            price=Decimal('50.00'),
        )

        self.wallet.balance = Decimal('170.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-stop-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ) as send_push:
            result = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(result.stopped, 1)
        self.customer_profile.refresh_from_db()
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)
        self.assertEqual(send_push.call_count, 1)
        _tokens, _title, _body, data = send_push.call_args[0]
        self.assertEqual(data['type'], 'wallet_meal_stop')
        self.assertEqual(data['screen'], 'wallet')

        qs = eligible_delivery_queryset(self.business_date, OrderDelivery.MealPeriod.LUNCH)
        self.assertFalse(qs.filter(pk=delivery.pk).exists())

        # Admin manual mark still works.
        mark_delivery(delivery, OrderDelivery.DeliveryStatus.DELIVERED, marked_by=self.admin_user)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)

    def test_resume_on_credit_and_dry_run_mutates_nothing(self):
        self._subscribe()
        apply_meal_service_block(self.customer_profile)
        self.customer_profile.refresh_from_db()
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)

        self.wallet.balance = Decimal('250.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])

        dry = run_wallet_threshold_check(as_of=self.business_date, dry_run=True)
        self.assertEqual(dry.resumed, 1)
        self.customer_profile.refresh_from_db()
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)
        self.assertEqual(len(mail.outbox), 0)

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ):
            live = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)
        self.assertEqual(live.resumed, 1)
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)

        # Credit path also resumes (on_commit runs after credit_wallet's atomic block).
        apply_meal_service_block(self.customer_profile)
        self.wallet.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            credit_wallet(self.wallet, Decimal('10.00'))
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)

    def test_admin_summary_and_batch_isolation(self):
        self._subscribe()
        self.wallet.balance = Decimal('180.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-device-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            side_effect=RuntimeError('fcm boom'),
        ):
            result = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(result.stopped, 1)
        self.assertGreaterEqual(len(result.affected), 1)
        admin_mails = [m for m in mail.outbox if 'Low balance users report' in m.subject]
        self.assertEqual(len(admin_mails), 1)
        self.assertIn('thresh_admin@example.com', admin_mails[0].to)
        self.assertIn('Meal Stopped', admin_mails[0].body)

    def test_management_command_dry_run(self):
        self._subscribe()
        self.wallet.balance = Decimal('290.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        call_command(
            'check_wallet_balance_thresholds',
            '--date',
            self.business_date.isoformat(),
            '--dry-run',
        )
        self.customer_profile.refresh_from_db()
        self.assertIsNone(self.customer_profile.last_low_balance_reminder_on)
        self.assertEqual(len(mail.outbox), 0)
