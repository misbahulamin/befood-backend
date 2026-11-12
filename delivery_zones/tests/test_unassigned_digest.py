from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from delivery_zones.services.locations import create_location
from delivery_zones.services.unassigned_digest import (
    build_unassigned_digest_rows,
    format_subscription_time,
    notify_admins_unassigned_delivery_digest,
    run_unassigned_delivery_digest,
    unassigned_active_subscriptions_queryset,
)
from delivery_zones.services.zones import create_zone
from meals.models import MealCategory
from orders.models import CustomerSubscription
from user_management.models import AdminProfile, CustomerProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _make_customer(username, phone, *, email=None, first_name=None):
    user = User.objects.create_user(
        username=username,
        email=email if email is not None else f'{username}@example.com',
        password='StrongPassword123',
        first_name=first_name or username.title(),
        is_active=True,
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    return CustomerProfile.objects.create(
        user=user,
        phone=phone,
        is_email_verified=True,
    )


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    TIME_ZONE='Asia/Dhaka',
)
class UnassignedDigestQueryTests(TestCase):
    def setUp(self):
        self.plan = MealCategory.objects.create(
            meal_name='Digest Plan',
            total_price=Decimal('150.00'),
            meal_thumbnail=make_test_image('digest.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        self.zone = create_zone(name='Digest Zone', code='digest-z1', priority=1)
        self.location = create_location(
            name='Digest Loc', zone_public_id=self.zone.public_id, priority=1
        )
        self.default_sub = self.location.sub_locations.get(is_default=True)

    def _subscribe(self, customer, *, status=CustomerSubscription.Status.ACTIVE):
        return CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=status,
            started_on=date(2026, 11, 1),
        )

    def test_includes_active_null_sub_location(self):
        customer = _make_customer('digest_unassigned', '1718000101')
        sub = self._subscribe(customer)
        self.assertIsNone(customer.delivery_sub_location_id)

        rows = build_unassigned_digest_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].customer_id, customer.pk)
        self.assertEqual(
            list(unassigned_active_subscriptions_queryset().values_list('pk', flat=True)),
            [sub.pk],
        )

    def test_excludes_active_assigned_sub_location(self):
        customer = _make_customer('digest_assigned', '1718000102')
        customer.delivery_sub_location = self.default_sub
        customer.delivery_location = self.location
        customer.save(update_fields=['delivery_sub_location', 'delivery_location', 'updated_at'])
        self._subscribe(customer)

        self.assertEqual(build_unassigned_digest_rows(), [])

    def test_excludes_cancelled_subscription(self):
        customer = _make_customer('digest_cancelled', '1718000103')
        self._subscribe(customer, status=CustomerSubscription.Status.CANCELLED)

        self.assertEqual(build_unassigned_digest_rows(), [])

    def test_mirrored_location_without_sub_still_unassigned(self):
        customer = _make_customer('digest_bridge', '1718000104')
        customer.delivery_location = self.location
        customer.delivery_sub_location = None
        customer.save(update_fields=['delivery_location', 'delivery_sub_location', 'updated_at'])
        self._subscribe(customer)

        rows = build_unassigned_digest_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].customer_id, customer.pk)

    def test_ordered_by_created_at(self):
        older = _make_customer('digest_old', '1718000105')
        newer = _make_customer('digest_new', '1718000106')
        sub_old = self._subscribe(older)
        sub_new = self._subscribe(newer)
        CustomerSubscription.objects.filter(pk=sub_old.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        CustomerSubscription.objects.filter(pk=sub_new.pk).update(
            created_at=timezone.now() - timedelta(hours=1)
        )

        ids = list(
            unassigned_active_subscriptions_queryset().values_list('customer_id', flat=True)
        )
        self.assertEqual(ids, [older.pk, newer.pk])

    def test_subscription_time_asia_dhaka(self):
        utc = ZoneInfo('UTC')
        created = datetime(2026, 11, 12, 12, 0, 0, tzinfo=utc)
        formatted = format_subscription_time(created)
        self.assertTrue(formatted.startswith('2026-11-12T18:00:00'))
        self.assertIn('+06:00', formatted)


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@befood.test',
    TIME_ZONE='Asia/Dhaka',
)
class UnassignedDigestEmailTests(TestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='digest_admin',
            email='digest_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)

        self.plan = MealCategory.objects.create(
            meal_name='Digest Email Plan',
            total_price=Decimal('150.00'),
            meal_thumbnail=make_test_image('digest_email.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )

    def _subscribe(self, customer):
        return CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 11, 1),
        )

    def test_non_empty_email_has_required_columns_and_recipients(self):
        customer = _make_customer(
            'digest_mail_user',
            '1718000201',
            email='digest_mail_user@example.com',
            first_name='Karim',
        )
        self._subscribe(customer)
        rows = build_unassigned_digest_rows()

        sent = notify_admins_unassigned_delivery_digest(rows=rows, dry_run=False)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn(self.admin_user.email, message.to)
        self.assertIn('Unassigned delivery subscribers (1)', message.subject)
        body = message.body
        self.assertIn('Karim', body)
        self.assertIn('Name', body)
        self.assertIn('Phone', body)
        self.assertIn('Subscription Time', body)
        self.assertIn('Email', body)
        self.assertIn('digest_mail_user@example.com', body)
        html = message.alternatives[0][0]
        self.assertIn('<table', html)
        self.assertIn('Karim', html)
        self.assertNotIn('password', body.lower())
        self.assertNotIn('token', body.lower())

    def test_missing_contact_fields_use_placeholders(self):
        customer = _make_customer(
            'digest_na',
            None,
            email='',
            first_name='NoContact',
        )
        # phone unique allows null; clear email on user
        customer.user.email = ''
        customer.user.save(update_fields=['email'])
        self._subscribe(customer)
        rows = build_unassigned_digest_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].phone, 'N/A')
        self.assertEqual(rows[0].email, 'N/A')

        notify_admins_unassigned_delivery_digest(rows=rows, dry_run=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('N/A', mail.outbox[0].body)

    def test_empty_run_sends_summary(self):
        sent = notify_admins_unassigned_delivery_digest(rows=[], dry_run=False)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('none pending', mail.outbox[0].subject.lower())
        self.assertIn('No unassigned active subscribers', mail.outbox[0].body)

    def test_dry_run_does_not_send(self):
        customer = _make_customer('digest_dry', '1718000202')
        self._subscribe(customer)
        rows = build_unassigned_digest_rows()
        sent = notify_admins_unassigned_delivery_digest(rows=rows, dry_run=True)
        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@befood.test',
    TIME_ZONE='Asia/Dhaka',
)
class UnassignedDigestRunHelperTests(TestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='digest_run_admin',
            email='digest_run_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)

        self.plan = MealCategory.objects.create(
            meal_name='Digest Run Plan',
            total_price=Decimal('150.00'),
            meal_thumbnail=make_test_image('digest_run.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )

    def test_run_result_shape_and_slot(self):
        customer = _make_customer('digest_run_user', '1718000301')
        CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 11, 1),
        )

        result = run_unassigned_delivery_digest(dry_run=False, slot='evening')
        payload = result.as_log_dict()
        self.assertEqual(
            set(payload.keys()),
            {'dry_run', 'slot', 'candidate_count', 'email_sent', 'errors'},
        )
        self.assertFalse(payload['dry_run'])
        self.assertEqual(payload['slot'], 'evening')
        self.assertEqual(payload['candidate_count'], 1)
        self.assertTrue(payload['email_sent'])
        self.assertEqual(payload['errors'], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_run_dry_run_skips_email(self):
        customer = _make_customer('digest_run_dry', '1718000302')
        CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 11, 1),
        )
        result = run_unassigned_delivery_digest(dry_run=True, slot='night')
        self.assertEqual(result.candidate_count, 1)
        self.assertFalse(result.email_sent)
        self.assertEqual(result.slot, 'night')
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@befood.test',
    TIME_ZONE='Asia/Dhaka',
)
class UnassignedDigestCommandTests(TestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='digest_cmd_admin',
            email='digest_cmd_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)

        self.plan = MealCategory.objects.create(
            meal_name='Digest Cmd Plan',
            total_price=Decimal('150.00'),
            meal_thumbnail=make_test_image('digest_cmd.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )

    def test_command_success_path_sends_email(self):
        customer = _make_customer('digest_cmd_user', '1718000401', first_name='Salma')
        CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 11, 1),
        )
        call_command('send_unassigned_delivery_digest', slot='evening')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Salma', mail.outbox[0].body)

    def test_command_empty_path_sends_summary(self):
        call_command('send_unassigned_delivery_digest')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No unassigned active subscribers', mail.outbox[0].body)

    def test_command_dry_run_no_mail(self):
        customer = _make_customer('digest_cmd_dry', '1718000402')
        CustomerSubscription.objects.create(
            customer=customer,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 11, 1),
        )
        call_command('send_unassigned_delivery_digest', dry_run=True, slot='night')
        self.assertEqual(len(mail.outbox), 0)


class ManagedCronInstallerDigestTests(TestCase):
    def test_installer_contains_digest_utc_schedules_without_cron_tz(self):
        root = Path(__file__).resolve().parents[2]
        installer = (root / 'scripts' / 'cron' / 'install_managed_cron.sh').read_text(
            encoding='utf-8'
        )
        wrapper = root / 'scripts' / 'cron' / 'run_unassigned_delivery_digest.sh'
        self.assertTrue(wrapper.exists())
        wrapper_text = wrapper.read_text(encoding='utf-8')

        self.assertIn('run_unassigned_delivery_digest.sh', installer)
        self.assertIn('0 12 * * *', installer)
        self.assertIn('0 16 * * *', installer)
        self.assertIn('18:00', installer)
        self.assertIn('22:00', installer)
        self.assertIn('0 9 * * *', installer)
        self.assertIn('0 17 * * *', installer)
        self.assertIn('0 2 * * *', installer)
        self.assertIn('0 14 * * *', installer)
        # Comments may mention CRON_TZ; the installer must not emit an assignment.
        self.assertNotIn('CRON_TZ=', installer)
        self.assertIn('CRON_TZ is not used', installer)

        self.assertTrue(wrapper_text.startswith('#!/usr/bin/env bash'))
        self.assertNotIn('\r', wrapper_text)
        self.assertIn('_cron_env.sh', wrapper_text)
        self.assertIn('PYTHON_BIN=', wrapper_text)
        self.assertIn('send_unassigned_delivery_digest', wrapper_text)
        self.assertIn('cron-unassigned-delivery-digest.log', wrapper_text)
        self.assertIn('flock', wrapper_text)
        self.assertNotIn('python manage.py', wrapper_text)
        self.assertIn('${PYTHON_BIN}', wrapper_text)
