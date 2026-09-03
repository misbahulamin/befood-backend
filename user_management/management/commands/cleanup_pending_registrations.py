"""Delete expired pending customer registrations."""

from django.core.management.base import BaseCommand

from user_management.services.pending_registration import cleanup_expired_pending_registrations


class Command(BaseCommand):
    help = (
        'Delete expired PendingCustomerRegistration rows. '
        'Safe to run periodically via cron (e.g. hourly).'
    )

    def handle(self, *args, **options):
        deleted = cleanup_expired_pending_registrations()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} expired pending registration(s).'))
