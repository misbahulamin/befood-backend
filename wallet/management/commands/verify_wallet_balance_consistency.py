from django.core.management.base import BaseCommand, CommandError

from wallet.models import Wallet
from wallet.services.ledger import assert_wallet_invariant, WalletBalanceInvariantError


class Command(BaseCommand):
    help = 'Verify every wallet satisfies balance == recharge_balance + commission_balance.'

    def handle(self, *args, **options):
        errors = []
        for wallet in Wallet.objects.all().iterator():
            try:
                assert_wallet_invariant(wallet)
            except WalletBalanceInvariantError as exc:
                errors.append(str(exc))
        if errors:
            for err in errors[:50]:
                self.stderr.write(err)
            raise CommandError(
                f'Wallet balance consistency failed for {len(errors)} wallet(s).'
            )
        self.stdout.write(
            self.style.SUCCESS(
                f'OK: {Wallet.objects.count()} wallet(s) satisfy the bucket invariant.'
            )
        )
