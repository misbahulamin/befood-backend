"""Backfill MealProfitTransaction rows for historical charged deliveries."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from admin_wallet.models import MealProfitTransaction
from admin_wallet.services.profit import meal_profit_recognized
from admin_wallet.services.profit_ledger import recognize_meal_profit
from orders.models import OrderDelivery

_MONEY = Decimal('0.01')


class Command(BaseCommand):
    help = (
        'Create missing MealProfitTransaction rows for charged OrderDelivery records. '
        'Idempotent. Live recognition uses service_date; legacy wallet profit used '
        'OrderDelivery.updated_at — --validate reports both axes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report candidates without inserting rows.',
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help=(
                'After backfill (or alone), compare ledger Sum(profit_amount) to '
                'legacy meal_profit_recognized() and print axis notes.'
            ),
        )
        parser.add_argument(
            '--start-date',
            type=str,
            default=None,
            help='Optional service_date lower bound YYYY-MM-DD.',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            default=None,
            help='Optional service_date upper bound YYYY-MM-DD.',
        )

    def handle(self, *args, **options):
        start = self._parse_date(options.get('start_date'))
        end = self._parse_date(options.get('end_date'))
        dry_run = options['dry_run']
        validate = options['validate']

        qs = OrderDelivery.objects.filter(
            payment_status=OrderDelivery.PaymentStatus.CHARGED,
            charged_amount__isnull=False,
            meal_profit_transaction__isnull=True,
        ).select_related(
            'order',
            'order__customer',
            'order__meal',
            'subscription',
            'subscription__customer',
            'subscription__meal',
        )
        if start is not None:
            qs = qs.filter(service_date__gte=start)
        if end is not None:
            qs = qs.filter(service_date__lte=end)

        candidate_count = qs.count()
        self.stdout.write(f'Candidates missing profit rows: {candidate_count}')

        created = 0
        skipped = 0
        if not dry_run:
            for delivery in qs.iterator(chunk_size=200):
                row = recognize_meal_profit(
                    delivery,
                    source=MealProfitTransaction.Source.BACKFILL,
                )
                if row is not None:
                    created += 1
                else:
                    skipped += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created={created} skipped_unresolvable={skipped}'
                )
            )
        else:
            self.stdout.write(self.style.WARNING('Dry-run: no rows written.'))

        if validate:
            self._validate(start=start, end=end)

    def _validate(self, *, start, end):
        ledger_qs = MealProfitTransaction.objects.all()
        if start is not None:
            ledger_qs = ledger_qs.filter(service_date__gte=start)
        if end is not None:
            ledger_qs = ledger_qs.filter(service_date__lte=end)

        ledger_total = (
            ledger_qs.aggregate(total=Sum('profit_amount'))['total'] or Decimal('0.00')
        )
        ledger_total = Decimal(ledger_total).quantize(_MONEY)

        # Legacy live calculator filters by updated_at; for bounded compare we only
        # have service_date bounds on the CLI — report lifetime live vs ledger range.
        live_total = meal_profit_recognized()

        self.stdout.write('')
        self.stdout.write('=== Validation ===')
        self.stdout.write(
            'Note: ledger analytics use service_date; legacy meal_profit_recognized '
            'uses OrderDelivery.updated_at. Totals may differ slightly when charge '
            'day != service day.'
        )
        self.stdout.write(f'Ledger profit (service_date window): {ledger_total}')
        self.stdout.write(f'Legacy live profit (lifetime updated_at): {live_total}')
        delta = (ledger_total - live_total).quantize(_MONEY)
        self.stdout.write(f'Delta (ledger - live lifetime): {delta}')
        missing = OrderDelivery.objects.filter(
            payment_status=OrderDelivery.PaymentStatus.CHARGED,
            charged_amount__isnull=False,
            meal_profit_transaction__isnull=True,
        ).count()
        self.stdout.write(f'Charged deliveries still missing profit rows: {missing}')

    def _parse_date(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('Invalid date; use YYYY-MM-DD.') from exc
