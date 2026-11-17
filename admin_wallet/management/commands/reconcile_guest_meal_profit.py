"""Reconcile missing MealProfitTransaction rows for delivered GuestMealOrders."""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef

from admin_wallet.models import MealProfitTransaction
from admin_wallet.services.profit_ledger import recognize_guest_meal_profit
from orders.models import GuestMealOrder


class Command(BaseCommand):
    help = (
        'Find delivered GuestMealOrder rows missing profit realization and '
        'optionally create ledger rows. Dry-run by default; pass --apply to write.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Create missing guest profit rows (otherwise dry-run only).',
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
        apply_writes = options['apply']

        has_profit = MealProfitTransaction.objects.filter(
            guest_meal_order_id=OuterRef('pk'),
            meal_kind=MealProfitTransaction.MealKind.GUEST,
        )
        qs = (
            GuestMealOrder.objects.filter(status=GuestMealOrder.Status.DELIVERED)
            .annotate(_has_profit=Exists(has_profit))
            .filter(_has_profit=False)
            .select_related('subscription__meal', 'customer', 'subscription', 'delivery')
            .order_by('service_date', 'id')
        )
        if start is not None:
            qs = qs.filter(service_date__gte=start)
        if end is not None:
            qs = qs.filter(service_date__lte=end)

        candidates = list(qs)
        self.stdout.write(f'Delivered guest orders missing profit rows: {len(candidates)}')
        for order in candidates:
            self.stdout.write(
                f'  - {order.public_id} service_date={order.service_date} '
                f'period={order.meal_period} qty={order.quantity} '
                f'total={order.total_amount}'
            )

        if not apply_writes:
            self.stdout.write(self.style.WARNING('Dry-run: no rows written. Pass --apply to create.'))
            return

        created = 0
        skipped = 0
        for order in candidates:
            row = recognize_guest_meal_profit(
                order,
                source=MealProfitTransaction.Source.GUEST_BACKFILL,
            )
            if row is not None:
                created += 1
            else:
                skipped += 1
        self.stdout.write(
            self.style.SUCCESS(f'Created={created} skipped_unresolvable={skipped}')
        )

    def _parse_date(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError as exc:
            raise CommandError('Invalid date; use YYYY-MM-DD.') from exc
