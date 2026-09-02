from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from orders.services.wallet_balance_thresholds import (
    WalletThresholdRunResult,
    business_today,
    run_wallet_threshold_check,
)


class Command(BaseCommand):
    help = (
        'Evaluate customer wallet balances against reminder and meal-stop thresholds, '
        'notify customers, block/resume meal service, and email admins a summary. '
        'Intended for cron at 08:00 / 20:00 Asia/Dhaka.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Business date YYYY-MM-DD (defaults to meal-off timezone business today).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report actions only; do not mutate block state or send notifications.',
        )

    def handle(self, *args, **options):
        as_of = None
        if options['date']:
            try:
                as_of = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError as exc:
                raise CommandError('Invalid --date; use YYYY-MM-DD.') from exc
        else:
            as_of = business_today()

        result: WalletThresholdRunResult = run_wallet_threshold_check(
            as_of=as_of,
            dry_run=options['dry_run'],
        )
        self._print_summary(result)

    def _print_summary(self, result: WalletThresholdRunResult) -> None:
        payload = result.as_log_dict()
        line = (
            f"check_wallet_balance_thresholds business_date={payload['business_date']} "
            f"dry_run={payload['dry_run']} evaluated={payload['evaluated']} "
            f"reminded={payload['reminded']} stopped={payload['stopped']} "
            f"resumed={payload['resumed']} errors={payload['errors']} "
            f"affected={payload['affected_count']}"
        )
        self.stdout.write(line)
        for row in result.affected:
            self.stdout.write(
                f"  {row.status}: customer_id={row.customer_id} name={row.name} "
                f"balance={row.balance:.2f} package={row.package_name}"
            )
