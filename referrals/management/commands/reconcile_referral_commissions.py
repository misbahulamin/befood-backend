from django.core.management.base import BaseCommand

from referrals.models import ReferralCommission, ReferralRelationship
from referrals.services.commission import credit_referral_commission_for_delivery
from referrals.services.eligibility import is_retryable_skip


class Command(BaseCommand):
    help = (
        'Retry failed referral commissions and backfill/upgrade missing accruals '
        'using co-consumption eligibility (both active; referrer delivered same '
        'date/period; referred delivered+charged). '
        'Always run with --dry-run first in production before write runs/cron.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=(
                'Report planned retries/backfills/upgrades without wallet or '
                'commission money writes. Recommended before production cron.'
            ),
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'DRY-RUN: no wallet or commission money movements will be written.'
                )
            )

        retried = 0
        failed = list(
            ReferralCommission.objects.filter(status=ReferralCommission.Status.FAILED)
            .select_related('order_delivery')
            .order_by('id')[:limit]
        )
        for row in failed:
            delivery = row.order_delivery
            if delivery is None:
                continue
            if dry_run:
                self.stdout.write(
                    f'would_retry_failed commission_id={row.pk} '
                    f'delivery_id={delivery.pk}'
                )
                retried += 1
                continue
            # Historical note: SUCCESS rows from the pre-co-consumption rule are
            # never auto-reversed here; clawback uses admin reverse / approved ops.
            row.delete()
            credit_referral_commission_for_delivery(delivery)
            retried += 1

        from orders.models import OrderDelivery
        from orders.services.subscription_parent import delivery_customer

        missing = 0
        upgraded = 0
        deliveries = OrderDelivery.objects.filter(
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            payment_status=OrderDelivery.PaymentStatus.CHARGED,
        ).order_by('-id')[: limit * 5]
        for delivery in deliveries:
            customer = delivery_customer(delivery)
            if customer is None:
                continue
            if not ReferralRelationship.objects.filter(referred=customer).exists():
                continue

            existing = (
                ReferralCommission.objects.filter(
                    order_delivery=delivery,
                    is_manual=False,
                    reversal_of__isnull=True,
                )
                .exclude(status=ReferralCommission.Status.PENDING)
                .order_by('id')
                .first()
            )
            if existing is not None and not is_retryable_skip(existing):
                continue

            if dry_run:
                action = 'would_upgrade_skip' if existing is not None else 'would_backfill'
                self.stdout.write(
                    f'{action} delivery_id={delivery.pk} '
                    f'commission_id={getattr(existing, "pk", None)}'
                )
                if existing is not None:
                    upgraded += 1
                else:
                    missing += 1
                if (missing + upgraded) >= limit:
                    break
                continue

            before_pk = existing.pk if existing is not None else None
            before_status = existing.status if existing is not None else None
            row = credit_referral_commission_for_delivery(delivery)
            if row is None:
                continue
            if before_pk is not None and row.pk == before_pk:
                if (
                    before_status == ReferralCommission.Status.SKIPPED
                    and row.status == ReferralCommission.Status.SUCCESS
                ):
                    upgraded += 1
            elif before_pk is None and row.status in (
                ReferralCommission.Status.SUCCESS,
                ReferralCommission.Status.FAILED,
                ReferralCommission.Status.SKIPPED,
            ):
                missing += 1
            if (missing + upgraded) >= limit:
                break

        # Also retry meal-mismatch skips explicitly within limit (same eligibility).
        if not dry_run:
            skip_rows = list(
                ReferralCommission.objects.filter(
                    status=ReferralCommission.Status.SKIPPED,
                    status_reason='REFERRER_MEAL_NOT_CONSUMED',
                    is_manual=False,
                    order_delivery__isnull=False,
                )
                .select_related('order_delivery')
                .order_by('id')[:limit]
            )
            for row in skip_rows:
                delivery = row.order_delivery
                if delivery is None:
                    continue
                updated = credit_referral_commission_for_delivery(delivery)
                if (
                    updated is not None
                    and updated.pk == row.pk
                    and updated.status == ReferralCommission.Status.SUCCESS
                ):
                    upgraded += 1
        else:
            skip_count = ReferralCommission.objects.filter(
                status=ReferralCommission.Status.SKIPPED,
                status_reason='REFERRER_MEAL_NOT_CONSUMED',
                is_manual=False,
                order_delivery__isnull=False,
            ).count()
            self.stdout.write(
                f'would_recheck_meal_mismatch_skips count={skip_count} (capped by --limit on write)'
            )

        style = self.style.WARNING if dry_run else self.style.SUCCESS
        prefix = 'DRY-RUN ' if dry_run else ''
        self.stdout.write(
            style(
                f'{prefix}Retried failed={retried}, backfilled missing={missing}, '
                f'upgraded skips={upgraded}'
            )
        )
        self.stdout.write(
            'Note: historical SUCCESS commissions are not auto-reversed; '
            'use admin reverse or an approved one-off for clawback.'
        )
