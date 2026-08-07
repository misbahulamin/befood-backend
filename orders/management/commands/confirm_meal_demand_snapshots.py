from datetime import datetime

from django.core.management.base import BaseCommand

from orders.services.meal_demand import confirm_and_save_due_snapshots
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now


class Command(BaseCommand):
    help = (
        'Upsert MealDemandSnapshot rows for service slots whose meal-off deadline '
        'has passed (confirmed cooking demand + frozen ingredients).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lookback-days',
            type=int,
            default=7,
            help='How many calendar days before today to scan for confirmed slots (default: 7).',
        )
        parser.add_argument(
            '--now',
            type=str,
            default=None,
            help='Optional ISO datetime override in meal-off timezone (e.g. 2026-08-05T15:00:00).',
        )

    def handle(self, *args, **options):
        settings_obj = get_meal_off_settings()
        reference_now = None
        if options['now']:
            raw = options['now']
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                from zoneinfo import ZoneInfo

                parsed = parsed.replace(tzinfo=ZoneInfo(settings_obj.timezone))
            reference_now = parsed
        else:
            reference_now = meal_off_business_now(settings_obj)

        result = confirm_and_save_due_snapshots(
            reference_now=reference_now,
            lookback_days=options['lookback_days'],
            settings_obj=settings_obj,
        )
        self.stdout.write(
            self.style.SUCCESS(
                'Meal demand snapshots: '
                f"written={result['written']}, "
                f"skipped_estimated_slots={result['skipped_estimated']}, "
                f"lookback_days={result['lookback_days']}"
            )
        )
