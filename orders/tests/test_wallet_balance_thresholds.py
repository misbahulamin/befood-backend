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
from orders.models import CustomerSubscription, OrderDelivery, OrderWalletSettings
from orders.services.auto_meal_delivery import eligible_delivery_queryset
from orders.services.order_delivery import mark_delivery
from orders.services.subscription_service import cancel_subscription, subscribe_customer
from orders.services.wallet_balance_thresholds import (
    apply_meal_service_block,
    candidate_customers_queryset,
    clear_orphan_low_balance_blocks,
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
        _tokens, title, body, data = send_push.call_args[0]
        self.assertEqual(title, 'Low Wallet Balance Alert')
        self.assertIn('Hi Rahim', body)
        self.assertIn('your current wallet balance is low', body)
        self.assertEqual(data['type'], 'wallet_meal_stop')
        self.assertEqual(data['screen'], 'wallet')

        qs = eligible_delivery_queryset(self.business_date, OrderDelivery.MealPeriod.LUNCH)
        self.assertFalse(qs.filter(pk=delivery.pk).exists())

        # Admin manual mark still works.
        mark_delivery(delivery, OrderDelivery.DeliveryStatus.DELIVERED, marked_by=self.admin_user)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)

    def test_meal_stop_push_every_cron_run_while_below_threshold(self):
        self._subscribe()
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-stop-repeat-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ) as send_push:
            first = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)
            second = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(first.stopped, 1)
        self.assertEqual(second.stopped, 0)
        self.customer_profile.refresh_from_db()
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)
        self.assertEqual(send_push.call_count, 2)
        title = send_push.call_args_list[1][0][1]
        self.assertEqual(title, 'Low Wallet Balance Alert')

    def test_no_meal_stop_band_push_when_balance_at_or_above_threshold(self):
        self._subscribe()
        apply_meal_service_block(self.customer_profile)
        self.wallet.balance = Decimal('250.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-resume-no-alert',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ) as send_push:
            result = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(result.resumed, 1)
        meal_stop_pushes = [
            c for c in send_push.call_args_list if c[0][3].get('type') == 'wallet_meal_stop'
        ]
        self.assertEqual(meal_stop_pushes, [])
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)

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

    def test_candidate_queryset_excludes_blocked_non_subscribers(self):
        apply_meal_service_block(self.customer_profile)
        self.customer_profile.refresh_from_db()
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)
        self.assertFalse(
            candidate_customers_queryset().filter(pk=self.customer_profile.pk).exists()
        )

        subscription = self._subscribe()
        self.assertTrue(
            candidate_customers_queryset().filter(pk=self.customer_profile.pk).exists()
        )

        cancel_subscription(subscription, today=self.business_date, cancel_source='system')
        self.assertFalse(
            candidate_customers_queryset().filter(pk=self.customer_profile.pk).exists()
        )

    def test_cancel_clears_low_balance_block(self):
        subscription = self._subscribe()
        apply_meal_service_block(self.customer_profile)
        self.customer_profile.refresh_from_db()
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)

        cancel_subscription(subscription, today=self.business_date, cancel_source='system')
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)
        self.assertIsNone(self.customer_profile.meal_service_blocked_at)

        # Idempotent cancel does not re-raise or re-block.
        cancel_subscription(subscription, today=self.business_date, cancel_source='system')
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)

    def test_orphan_block_cleanup_silent_no_notify(self):
        apply_meal_service_block(self.customer_profile)
        self.wallet.balance = Decimal('50.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-orphan-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ) as send_push:
            cleared = clear_orphan_low_balance_blocks()
            result = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(cleared, 1)
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)
        self.assertEqual(result.evaluated, 0)
        self.assertEqual(result.affected, [])
        self.assertEqual(send_push.call_count, 0)
        customer_mails = [
            m
            for m in mail.outbox
            if self.customer_user.email in m.to
            and 'Low balance users report' not in m.subject
        ]
        self.assertEqual(customer_mails, [])
        admin_mails = [m for m in mail.outbox if 'Low balance users report' in m.subject]
        self.assertEqual(len(admin_mails), 1)
        self.assertIn('No low-balance or meal-stopped users', admin_mails[0].body)

    def test_cancelled_subscriber_omitted_from_admin_report_and_notify(self):
        subscription = self._subscribe()
        apply_meal_service_block(self.customer_profile)
        # Simulate pre-fix cancel that left the block flag set.
        CustomerSubscription.objects.filter(pk=subscription.pk).update(
            status=CustomerSubscription.Status.CANCELLED,
        )
        self.customer_profile.meal_service_blocked_low_balance = True
        self.customer_profile.save(
            update_fields=['meal_service_blocked_low_balance', 'updated_at']
        )
        self.wallet.balance = Decimal('50.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        DeviceToken.objects.create(
            user=self.customer_user,
            token='thresh-cancelled-token',
            platform=DeviceToken.Platform.ANDROID,
            is_active=True,
        )

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ) as send_push:
            result = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(result.evaluated, 0)
        self.assertEqual(result.stopped, 0)
        self.assertEqual(result.reminded, 0)
        self.assertEqual(result.affected, [])
        self.assertEqual(send_push.call_count, 0)
        self.customer_profile.refresh_from_db()
        self.assertFalse(self.customer_profile.meal_service_blocked_low_balance)

        admin_mails = [m for m in mail.outbox if 'Low balance users report' in m.subject]
        self.assertEqual(len(admin_mails), 1)
        self.assertNotIn('Rahim', admin_mails[0].body)
        self.assertIn('No low-balance or meal-stopped users', admin_mails[0].body)

    def test_active_subscriber_still_in_admin_report_with_package(self):
        self._subscribe()
        self.wallet.balance = Decimal('180.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])

        with patch(
            'notifications.services.wallet_threshold_notifications.send_to_tokens',
            return_value=[],
        ):
            result = run_wallet_threshold_check(as_of=self.business_date, dry_run=False)

        self.assertEqual(len(result.affected), 1)
        self.assertEqual(result.affected[0].package_name, 'Student Package')
        self.assertNotEqual(result.affected[0].package_name, 'N/A')

        admin_mails = [m for m in mail.outbox if 'Low balance users report' in m.subject]
        self.assertEqual(len(admin_mails), 1)
        self.assertIn('Student Package', admin_mails[0].body)
        self.assertIn('Total affected: 1', admin_mails[0].body)

    def test_dry_run_skips_orphan_cleanup_and_still_counts_active(self):
        apply_meal_service_block(self.customer_profile)
        self._subscribe()
        self.wallet.balance = Decimal('290.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])

        dry = run_wallet_threshold_check(as_of=self.business_date, dry_run=True)
        self.assertEqual(dry.reminded, 1)
        self.assertEqual(len(mail.outbox), 0)
        # Never-subscribed orphan would be a separate profile; active blocked stays.
        self.customer_profile.refresh_from_db()
        # Orphan cleanup must not run on dry-run; this profile is active so flag may
        # remain until a live stop/resume path — dry-run does not mutate blocks.
        self.assertTrue(self.customer_profile.meal_service_blocked_low_balance)
