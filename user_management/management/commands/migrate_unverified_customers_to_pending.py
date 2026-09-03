"""Migrate legacy inactive unverified customers into pending registrations."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from user_management.services.pending_registration import migrate_legacy_unverified_to_pending


class Command(BaseCommand):
    help = (
        'Convert legacy inactive unverified CustomerProfile users into '
        'PendingCustomerRegistration rows (deletes the inactive User). '
        'Use --dry-run to preview. After migration, users must complete '
        'email verification again (resend or re-register).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List candidates without mutating data.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        qs = (
            User.objects.filter(
                customer_profile__isnull=False,
                customer_profile__is_email_verified=False,
            )
            .select_related('customer_profile')
            .order_by('id')
        )
        count = qs.count()
        if dry_run:
            self.stdout.write(f'Would migrate {count} legacy unverified customer(s):')
            for user in qs[:50]:
                self.stdout.write(f'  - {user.email} (id={user.id})')
            if count > 50:
                self.stdout.write(f'  ... and {count - 50} more')
            return

        migrated = 0
        for user in list(qs):
            pending = migrate_legacy_unverified_to_pending(user)
            if pending is not None:
                migrated += 1
                self.stdout.write(f'Migrated {pending.email} → pending id={pending.id}')
        self.stdout.write(self.style.SUCCESS(f'Migrated {migrated} legacy unverified customer(s).'))
