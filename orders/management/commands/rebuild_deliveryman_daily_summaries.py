from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from orders.services.delivery_logistics import rebuild_daily_summaries


class Command(BaseCommand):
    help = (
        'Rebuild DeliveryManDailySummary rows from attributed OrderDelivery '
        'delivered/failed stops for a date range (inclusive).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='date_from', required=True, help='YYYY-MM-DD')
        parser.add_argument('--to', dest='date_to', required=True, help='YYYY-MM-DD')

    def handle(self, *args, **options):
        date_from = parse_date(options['date_from'])
        date_to = parse_date(options['date_to'])
        if date_from is None or date_to is None:
            raise CommandError('Invalid --from/--to; use YYYY-MM-DD.')
        if date_to < date_from:
            raise CommandError('--to must be on or after --from.')
        count = rebuild_daily_summaries(date_from=date_from, date_to=date_to)
        self.stdout.write(
            self.style.SUCCESS(
                f'Rebuilt {count} daily summary row(s) from {date_from} to {date_to}.'
            )
        )
