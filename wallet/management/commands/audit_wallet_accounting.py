"""
Read-only wallet accounting audit for provider-ref uniqueness and Admin Wallet types.

Run before deploying the live-status unique constraint migration:
  python manage.py audit_wallet_accounting

Exit code 1 if any pending/completed provider recharge duplicates exist.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Count

from admin_wallet.models import AdminWalletTransaction
from wallet.models import WalletTransaction

PROVIDER_METHODS = [
    WalletTransaction.Method.BKASH,
    WalletTransaction.Method.NAGAD,
    WalletTransaction.Method.BANK,
]
LIVE_STATUSES = [
    WalletTransaction.Status.PENDING,
    WalletTransaction.Status.COMPLETED,
]


class Command(BaseCommand):
    help = (
        'Read-only audit: live provider-ref duplicates, failed-ref reuse candidates, '
        'and Admin Wallet completed type counts (customer_withdraw vs expenses).'
    )

    def handle(self, *args, **options):
        blocking = False

        self.stdout.write(self.style.MIGRATE_HEADING('=== 1. Live provider-ref duplicates ==='))
        live_dupes = (
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.RECHARGE,
                method__in=PROVIDER_METHODS,
                status__in=LIVE_STATUSES,
            )
            .exclude(external_ref='')
            .values('method', 'external_ref')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
            .order_by('-cnt')
        )
        live_rows = list(live_dupes)
        if live_rows:
            blocking = True
            self.stdout.write(
                self.style.ERROR(
                    f'BLOCKING: {len(live_rows)} duplicate (method, external_ref) '
                    'group(s) among pending+completed provider recharges.'
                )
            )
            for row in live_rows[:20]:
                self.stdout.write(
                    f"  {row['method']}:{row['external_ref']} ×{row['cnt']}"
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'OK: no pending/completed provider recharge duplicates.'
                )
            )

        self.stdout.write(self.style.MIGRATE_HEADING('=== 2. Failed provider recharges ==='))
        failed_count = WalletTransaction.objects.filter(
            type=WalletTransaction.Type.RECHARGE,
            method__in=PROVIDER_METHODS,
            status=WalletTransaction.Status.FAILED,
        ).exclude(external_ref='').count()
        self.stdout.write(f'Failed provider recharges with non-empty external_ref: {failed_count}')

        # Same ref appears as failed AND as a live (pending/completed) row.
        failed_refs = (
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.RECHARGE,
                method__in=PROVIDER_METHODS,
                status=WalletTransaction.Status.FAILED,
            )
            .exclude(external_ref='')
            .values_list('method', 'external_ref')
            .distinct()
        )
        reused_after_fail = 0
        samples = []
        for method, external_ref in failed_refs.iterator():
            live = WalletTransaction.objects.filter(
                type=WalletTransaction.Type.RECHARGE,
                method=method,
                external_ref=external_ref,
                status__in=LIVE_STATUSES,
            ).exists()
            if live:
                reused_after_fail += 1
                if len(samples) < 10:
                    samples.append(f'{method}:{external_ref}')
        self.stdout.write(
            f'Failed refs that also have a live pending/completed row: {reused_after_fail}'
        )
        for s in samples:
            self.stdout.write(f'  sample: {s}')

        # Failed-only refs (candidates for reuse after this fix).
        failed_only = 0
        for method, external_ref in failed_refs.iterator():
            live = WalletTransaction.objects.filter(
                type=WalletTransaction.Type.RECHARGE,
                method=method,
                external_ref=external_ref,
                status__in=LIVE_STATUSES,
            ).exists()
            if not live:
                failed_only += 1
        self.stdout.write(
            f'Failed-only provider refs (reuse candidates after fix): {failed_only}'
        )

        self.stdout.write(
            self.style.MIGRATE_HEADING('=== 3. Admin Wallet completed types ===')
        )
        type_counts = (
            AdminWalletTransaction.objects.filter(
                status=AdminWalletTransaction.Status.COMPLETED,
            )
            .values('type')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        expense_total = 0
        withdraw_total = 0
        for row in type_counts:
            t = row['type']
            c = row['cnt']
            self.stdout.write(f'  {t}: {c}')
            if t == AdminWalletTransaction.Type.CUSTOMER_WITHDRAW:
                withdraw_total = c
            if t in AdminWalletTransaction.EXPENSE_TYPES:
                expense_total += c

        self.stdout.write(f'Completed customer_withdraw rows: {withdraw_total}')
        self.stdout.write(f'Completed EXPENSE_TYPES rows (sum): {expense_total}')

        # Spot-check: withdraws linked to customer wallet txns must be customer_withdraw.
        linked_withdraws = AdminWalletTransaction.objects.filter(
            status=AdminWalletTransaction.Status.COMPLETED,
            customer_wallet_transaction__isnull=False,
            customer_wallet_transaction__type=WalletTransaction.Type.WITHDRAW,
        )
        wrong_type = linked_withdraws.exclude(
            type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
        ).count()
        linked_ok = linked_withdraws.filter(
            type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
        ).count()
        self.stdout.write(
            f'Admin rows linked to customer withdraw txns: '
            f'customer_withdraw={linked_ok}, other_types={wrong_type}'
        )
        if wrong_type:
            self.stdout.write(
                self.style.WARNING(
                    'WARNING: some customer-withdraw wallet txns have non-customer_withdraw '
                    'Admin Wallet types — investigate separately; do not auto-rewrite.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'OK: linked customer withdraws use type=customer_withdraw (not expense).'
                )
            )

        self.stdout.write(self.style.MIGRATE_HEADING('=== Summary ==='))
        if blocking:
            self.stdout.write(
                self.style.ERROR(
                    'FAIL: resolve live pending/completed duplicates before constraint migration.'
                )
            )
            raise SystemExit(1)
        self.stdout.write(
            self.style.SUCCESS(
                'PASS: safe to proceed with live-status uniqueness migration (this DB).'
            )
        )
