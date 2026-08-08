from django.core.management.base import BaseCommand

from inventory.services.queries import reconcile_items


class Command(BaseCommand):
    help = 'Reconcile inventory on-hand quantity against stock movement ledger sums.'

    def handle(self, *args, **options):
        drift = reconcile_items()
        if not drift:
            self.stdout.write(self.style.SUCCESS('No inventory stock drift detected.'))
            return
        self.stdout.write(
            self.style.ERROR(f'Found {len(drift)} item(s) with stock drift:')
        )
        for row in drift:
            self.stdout.write(
                f"- {row['name']} ({row['public_id']}): "
                f"on_hand={row['quantity_on_hand']} ledger_sum={row['ledger_sum']}"
            )
