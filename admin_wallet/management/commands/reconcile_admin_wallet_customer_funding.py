"""Backfill missing Admin Wallet custody rows for customer recharge/withdraw."""

from django.core.management.base import BaseCommand

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ingestion import (
    credit_from_customer_recharge,
    customer_recharge_idempotency_key,
    customer_withdraw_idempotency_key,
    debit_from_customer_withdraw,
)
from wallet.models import WalletTransaction


class Command(BaseCommand):
    help = (
        'Create missing Admin Wallet customer_funding credits and customer_withdraw '
        'debits for completed customer wallet recharge/withdraw transactions (idempotent). '
        'WARNING: If historical meal customer_payment cash credits already exist, '
        'backfilling funding can inflate Admin Wallet balance — review before running '
        'without --dry-run. Prefer forward-only cutover; do not also run '
        'reconcile_admin_wallet_meal_payments for cash backfill under custody accounting.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report missing custody rows without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        missing = 0
        created = 0

        recharges = (
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.RECHARGE,
                status=WalletTransaction.Status.COMPLETED,
                direction=WalletTransaction.Direction.CREDIT,
            )
            .select_related('wallet', 'wallet__customer')
            .order_by('id')
        )
        for txn in recharges.iterator():
            key = customer_recharge_idempotency_key(txn)
            exists = AdminWalletTransaction.objects.filter(
                idempotency_key=key,
                type=AdminWalletTransaction.Type.CUSTOMER_FUNDING,
            ).exists()
            if exists:
                continue
            missing += 1
            if dry_run:
                self.stdout.write(
                    f'Missing funding credit for recharge {txn.public_id} '
                    f'amount={txn.amount}'
                )
                continue
            credit_from_customer_recharge(txn)
            created += 1
            self.stdout.write(self.style.SUCCESS(f'Credited recharge {txn.public_id}'))

        withdraws = (
            WalletTransaction.objects.filter(
                type=WalletTransaction.Type.WITHDRAW,
                status=WalletTransaction.Status.COMPLETED,
                direction=WalletTransaction.Direction.DEBIT,
            )
            .select_related('wallet', 'wallet__customer')
            .order_by('id')
        )
        for txn in withdraws.iterator():
            key = customer_withdraw_idempotency_key(txn)
            exists = AdminWalletTransaction.objects.filter(
                idempotency_key=key,
                type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
            ).exists()
            if exists:
                continue
            missing += 1
            if dry_run:
                self.stdout.write(
                    f'Missing funding debit for withdraw {txn.public_id} '
                    f'amount={txn.amount}'
                )
                continue
            debit_from_customer_withdraw(txn)
            created += 1
            self.stdout.write(self.style.SUCCESS(f'Debited withdraw {txn.public_id}'))

        self.stdout.write(
            self.style.NOTICE(
                f'Done. missing={missing} created={created} dry_run={dry_run}'
            )
        )
