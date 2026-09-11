"""Read-only report of customer identity anomalies (no merges)."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from user_management.models import CustomerProfile


class Command(BaseCommand):
    help = (
        'Report suspected customer identity issues (duplicate emails, blank-email '
        'phone-only accounts, email accounts missing phone). Read-only: never merges '
        'or rewrites customer IDs, wallets, subscriptions, or referrals.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Max rows to print per section (default 50).',
        )

    def handle(self, *args, **options):
        limit = max(1, int(options['limit']))
        self.stdout.write(self.style.NOTICE('Customer identity report (read-only)'))
        self.stdout.write('No merges or ID rewrites are performed.\n')

        total = CustomerProfile.objects.count()
        phone_only = CustomerProfile.objects.filter(
            Q(user__email='') | Q(user__email__isnull=True)
        ).count()
        email_no_phone = CustomerProfile.objects.filter(
            Q(phone__isnull=True) | Q(phone=''),
            is_email_verified=True,
        ).count()
        self.stdout.write(f'Total CustomerProfile: {total}')
        self.stdout.write(f'Blank-email (phone-first style): {phone_only}')
        self.stdout.write(f'Verified email with null/blank phone: {email_no_phone}\n')

        self._report_duplicate_emails(limit)
        self._report_email_no_phone_sample(limit)
        self._report_phone_only_sample(limit)

        self.stdout.write(
            self.style.SUCCESS(
                '\nDone. Escalate suspected human duplicates via support playbook; '
                'do not auto-merge.'
            )
        )

    def _report_duplicate_emails(self, limit: int) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING('Duplicate User.email (case-insensitive)'))
        # Aggregate in Python for SQLite/Postgres portability on lower(email).
        buckets: dict[str, list[int]] = defaultdict(list)
        for user_id, email in (
            User.objects.filter(customer_profile__isnull=False)
            .exclude(email='')
            .values_list('id', 'email')
            .iterator()
        ):
            key = (email or '').strip().lower()
            if key:
                buckets[key].append(user_id)

        dupes = [(email, ids) for email, ids in buckets.items() if len(ids) > 1]
        if not dupes:
            self.stdout.write('  (none)')
            return
        for email, ids in sorted(dupes, key=lambda x: -len(x[1]))[:limit]:
            self.stdout.write(f'  {email}: user_ids={ids}')
        if len(dupes) > limit:
            self.stdout.write(f'  … {len(dupes) - limit} more')

    def _report_email_no_phone_sample(self, limit: int) -> None:
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                'Sample: verified email, missing phone (bind candidates)'
            )
        )
        qs = (
            CustomerProfile.objects.filter(
                Q(phone__isnull=True) | Q(phone=''),
                is_email_verified=True,
            )
            .select_related('user')
            .order_by('id')[:limit]
        )
        rows = list(qs)
        if not rows:
            self.stdout.write('  (none)')
            return
        for profile in rows:
            self.stdout.write(
                f'  customer_id={profile.pk} user_id={profile.user_id} '
                f'email={profile.user.email}'
            )

    def _report_phone_only_sample(self, limit: int) -> None:
        self.stdout.write(
            self.style.MIGRATE_HEADING('Sample: blank-email customers with phone')
        )
        qs = (
            CustomerProfile.objects.filter(Q(user__email='') | Q(user__email__isnull=True))
            .exclude(phone__isnull=True)
            .exclude(phone='')
            .select_related('user')
            .order_by('id')[:limit]
        )
        rows = list(qs)
        if not rows:
            self.stdout.write('  (none)')
            return
        for profile in rows:
            self.stdout.write(
                f'  customer_id={profile.pk} user_id={profile.user_id} phone={profile.phone}'
            )
