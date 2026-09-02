from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from orders.models import OrderDelivery
from orders.services.auto_meal_delivery import (
    AutoDeliveryRunResult,
    business_today,
    run_auto_delivery,
)


class Command(BaseCommand):
    help = (
        'Mark eligible scheduled meal deliveries as delivered for a lunch or dinner period '
        '(wallet charge via mark_delivery). Intended for cron at 15:00 / 23:00 Asia/Dhaka.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--meal-period',
            type=str,
            required=True,
            choices=[
                OrderDelivery.MealPeriod.LUNCH,
                OrderDelivery.MealPeriod.DINNER,
            ],
            help='lunch or dinner',
        )
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Service date YYYY-MM-DD (defaults to meal-off timezone business today).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List candidate count only; do not mutate deliveries or wallets.',
        )
        parser.add_argument(
            '--no-lock',
            action='store_true',
            help='Skip process lock (tests / emergency only).',
        )

    def handle(self, *args, **options):
        service_date = None
        if options['date']:
            try:
                service_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError as exc:
                raise CommandError('Invalid --date; use YYYY-MM-DD.') from exc
        else:
            service_date = business_today()

        result: AutoDeliveryRunResult = run_auto_delivery(
            service_date=service_date,
            meal_period=options['meal_period'],
            dry_run=options['dry_run'],
            acquire_lock=not options['no_lock'],
        )
        self._print_summary(result)
        if result.lock_busy:
            raise CommandError('Another auto-delivery run holds the process lock.')
        if result.disabled:
            self.stdout.write(self.style.WARNING('AUTO_MEAL_DELIVERY_ENABLED is False; no work done.'))

    def _print_summary(self, result: AutoDeliveryRunResult) -> None:
        payload = result.as_log_dict()
        line = (
            f"auto_deliver_meals service_date={payload['service_date']} "
            f"meal_period={payload['meal_period']} dry_run={payload['dry_run']} "
            f"disabled={payload['disabled']} lock_busy={payload['lock_busy']} "
            f"candidates={payload['candidate_count']} attempted={payload['attempted']} "
            f"delivered={payload['delivered']} already_delivered={payload['already_delivered']} "
            f"failed={payload['failed']}"
        )
        self.stdout.write(line)
        for failure in result.failures:
            self.stderr.write(
                f"  failure public_id={failure.delivery_public_id} "
                f"code={failure.code or 'UNKNOWN'} detail={failure.message}"
            )
