from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from onahar.services.contribution import close_month
from onahar.services.privacy import current_year_month


def previous_year_month(ref=None) -> str:
    ref = ref or timezone.localdate()
    year = ref.year
    month = ref.month - 1
    if month < 1:
        month = 12
        year -= 1
    return f'{year:04d}-{month:02d}'


class Command(BaseCommand):
    help = (
        'Idempotently close an Onahar calendar month: finalize contributions, '
        'expire remaining points, mark cycles closed. '
        'Schedule after month boundary, e.g. cron: 15 0 1 * * '
        '(01:15 on the 1st — Asia/Dhaka).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            default=None,
            help='YYYY-MM to close (default: previous calendar month)',
        )

    def handle(self, *args, **options):
        month = options['month'] or previous_year_month()
        if len(month) != 7 or month[4] != '-':
            raise CommandError('month must be YYYY-MM')
        if month == current_year_month():
            self.stdout.write(
                self.style.WARNING(
                    f'Closing the current month {month}; ensure this is intentional.'
                )
            )
        result = close_month(month)
        self.stdout.write(self.style.SUCCESS(f'close_onahar_month: {result}'))
