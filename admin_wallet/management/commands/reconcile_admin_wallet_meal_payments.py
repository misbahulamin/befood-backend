"""Backfill missing Admin Wallet credits for charged meal deliveries."""

from django.core.management.base import BaseCommand

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ingestion import (
    credit_from_meal_payment,
    meal_payment_idempotency_key,
)
from orders.models import OrderDelivery


class Command(BaseCommand):
    help = (
        'LEGACY / emergency only: create missing Admin Wallet customer_payment '
        'cash credits for charged deliveries. Under custody accounting '
        '(credit on customer recharge), this MUST stay unused — enabling it '
        'double-counts cash. Prefer reconcile_admin_wallet_customer_funding.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report missing credits without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        charged = (
            OrderDelivery.objects.filter(
                payment_status=OrderDelivery.PaymentStatus.CHARGED,
                wallet_transaction__isnull=False,
            )
            .select_related('order', 'order__customer', 'wallet_transaction')
            .order_by('id')
        )
        missing = 0
        created = 0
        for delivery in charged.iterator():
            key = meal_payment_idempotency_key(delivery)
            exists = AdminWalletTransaction.objects.filter(
                idempotency_key=key,
                type=AdminWalletTransaction.Type.CUSTOMER_PAYMENT,
            ).exists()
            if exists:
                continue
            missing += 1
            if dry_run:
                self.stdout.write(
                    f'Missing credit for delivery {delivery.public_id} '
                    f'amount={delivery.wallet_transaction.amount}'
                )
                continue
            credit_from_meal_payment(delivery, delivery.wallet_transaction)
            created += 1
            self.stdout.write(self.style.SUCCESS(f'Credited delivery {delivery.public_id}'))

        self.stdout.write(
            self.style.NOTICE(
                f'Done. missing={missing} created={created} dry_run={dry_run}'
            )
        )
