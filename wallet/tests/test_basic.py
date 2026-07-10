from django.contrib.auth.models import User
from django.test import TestCase
from wallet.models import Wallet
from wallet.services.ledger import credit_wallet, debit_wallet
from user_management.models import CustomerProfile

class WalletLedgerTest(TestCase):
    def test_credit_debit(self):
        user = User.objects.create_user(username='u1', password='x')
        customer = CustomerProfile.objects.create(user=user)
        wallet = Wallet.objects.create(customer=customer, balance=0)
        credit_wallet(wallet, 100)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 100)
        debit_wallet(wallet, 40)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 60)
