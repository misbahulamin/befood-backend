from django.core.management.base import BaseCommand, CommandError

from delivery_zones.services.unassigned_digest import (
    VALID_SLOTS,
    UnassignedDigestRunResult,
    run_unassigned_delivery_digest,
)


class Command(BaseCommand):
    help = (
        'Email verified admins a digest of active meal subscribers who still lack '
        'an operational delivery_sub_location. Intended for cron at 18:00 / 22:00 '
        'Asia/Dhaka.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report candidate count only; do not send email.',
        )
        parser.add_argument(
            '--slot',
            type=str,
            default=None,
            choices=sorted(VALID_SLOTS),
            help='Optional schedule label for logs (evening|night). Does not filter candidates.',
        )

    def handle(self, *args, **options):
        slot = options.get('slot')
        if slot is not None and slot not in VALID_SLOTS:
            raise CommandError('Invalid --slot; use evening or night.')

        result: UnassignedDigestRunResult = run_unassigned_delivery_digest(
            dry_run=options['dry_run'],
            slot=slot,
        )
        self._print_summary(result)
        if result.errors:
            raise CommandError(
                f'send_unassigned_delivery_digest completed with errors={result.errors}'
            )

    def _print_summary(self, result: UnassignedDigestRunResult) -> None:
        payload = result.as_log_dict()
        line = (
            f"send_unassigned_delivery_digest dry_run={payload['dry_run']} "
            f"slot={payload['slot']} candidate_count={payload['candidate_count']} "
            f"email_sent={payload['email_sent']} errors={payload['errors']}"
        )
        self.stdout.write(line)
        for row in result.rows:
            self.stdout.write(
                f"  customer_id={row.customer_id} name={row.name} "
                f"phone={row.phone} subscribed_at={row.subscription_time} "
                f"email={row.email}"
            )
