from django.db import transaction
from wallet.models import Wallet, WalletTransaction

@transaction.atomic
def credit_wallet(wallet: Wallet, amount, reference_type='', reference_id='', description=''):
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    wallet.balance += amount
    wallet.save(update_fields=['balance', 'updated_at'])
    return WalletTransaction.objects.create(wallet=wallet, type='credit', amount=amount, balance_after=wallet.balance, reference_type=reference_type, reference_id=reference_id, description=description)

@transaction.atomic
def debit_wallet(wallet: Wallet, amount, reference_type='', reference_id='', description=''):
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if wallet.balance < amount:
        raise ValueError('Insufficient balance')
    wallet.balance -= amount
    wallet.save(update_fields=['balance', 'updated_at'])
    return WalletTransaction.objects.create(wallet=wallet, type='debit', amount=amount, balance_after=wallet.balance, reference_type=reference_type, reference_id=reference_id, description=description)
