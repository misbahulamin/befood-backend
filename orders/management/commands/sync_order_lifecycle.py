from django.core.management.base import BaseCommand

from orders.models import Order
from orders.services.order_delivery import generate_order_deliveries, sync_order_lifecycle


class Command(BaseCommand):
    help = (
        'Activate due orders, mark expired slots as missed, complete finished packages, '
        'and optionally backfill missing delivery slots for non-cancelled orders.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--backfill-deliveries',
            action='store_true',
            help='Generate missing OrderDelivery rows for existing non-cancelled orders.',
        )
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Reference date YYYY-MM-DD (defaults to local today).',
        )

    def handle(self, *args, **options):
        reference_date = None
        if options['date']:
            from datetime import datetime

            reference_date = datetime.strptime(options['date'], '%Y-%m-%d').date()

        if options['backfill_deliveries']:
            count = 0
            qs = Order.objects.exclude(order_status=Order.OrderStatus.CANCELLED)
            for order in qs.iterator():
                before = order.deliveries.count()
                generate_order_deliveries(order)
                after = order.deliveries.count()
                if after > before:
                    count += 1
            self.stdout.write(self.style.SUCCESS(f'Backfilled deliveries for {count} order(s).'))

        result = sync_order_lifecycle(reference_date=reference_date)
        self.stdout.write(
            self.style.SUCCESS(
                'Lifecycle sync done: '
                f"activated={result['activated']}, "
                f"completed={result['completed']}, "
                f"closed_expired={result['closed_expired']}, "
                f"date={result['reference_date']}"
            )
        )
