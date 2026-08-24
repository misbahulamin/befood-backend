from datetime import datetime

from django.core.management.base import BaseCommand

from orders.services.subscription_service import ensure_all_active_subscription_deliveries


class Command(BaseCommand):
    help = (
        'Create missing rolling-horizon delivery slots for every active meal subscription. '
        'Run daily (cron) and after monthly menus are published.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Reference business date YYYY-MM-DD (defaults to meal-off timezone today).',
        )

    def handle(self, *args, **options):
        today = None
        if options['date']:
            today = datetime.strptime(options['date'], '%Y-%m-%d').date()
        count = ensure_all_active_subscription_deliveries(today=today)
        self.stdout.write(
            self.style.SUCCESS(
                f'Ensured deliveries for {count} active subscription(s).'
            )
        )
