from django.core.management.base import BaseCommand

from orders.services.delivery_address import backfill_missing_scheduled_snapshots


class Command(BaseCommand):
    help = (
        'Backfill delivery address snapshots on future scheduled OrderDelivery rows '
        'that are missing full_address snapshot text.'
    )

    def handle(self, *args, **options):
        updated = backfill_missing_scheduled_snapshots()
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} delivery snapshot(s).'))
