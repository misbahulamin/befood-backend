"""Phone-only identity must unlock customer wallet APIs without email verification."""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.services.ledger import get_or_create_platform_wallet
from orders.models import OrderWalletSettings
from user_management.models import CustomerProfile
from user_management.services.identity_verification import (
    IDENTITY_VERIFICATION_REQUIRED_WALLET_MESSAGE,
)
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def _set_meal_stop_threshold(amount: Decimal) -> None:
    settings_obj = OrderWalletSettings.load()
    settings_obj.meal_stop_threshold = amount
    settings_obj.save(update_fields=['meal_stop_threshold', 'updated_at'])


def _make_phone_only_customer(username='phone_u1', phone='1718888001'):
    """Mirror phone OTP registration: blank email, phone verified, CUSTOMER group."""
    user = User(username=username, email='')
    user.set_unusable_password()
    user.save()
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    now = timezone.now()
    profile = CustomerProfile.objects.create(
        user=user,
        phone=phone,
        is_email_verified=False,
        is_phone_verified=True,
        phone_verified_at=now,
        occupation=CustomerProfile.Occupation.STUDENT,
        is_bachelor=True,
    )
    return user, profile


def _make_unverified_customer(username='unverified_u1', phone='1718888002'):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='StrongPassword123',
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    profile = CustomerProfile.objects.create(
        user=user,
        phone=phone,
        is_email_verified=False,
        is_phone_verified=False,
        occupation=CustomerProfile.Occupation.STUDENT,
        is_bachelor=True,
    )
    return user, profile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PhoneVerifiedWalletAccessAPITests(APITestCase):
    def setUp(self):
        self.user, self.profile = _make_phone_only_customer()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.wallet_url = reverse('wallet:wallet-detail')
        self.recharge_url = reverse('wallet:wallet-recharge')
        self.withdraw_url = reverse('wallet:wallet-withdraw')
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('5000.00')
        platform.save(update_fields=['balance', 'updated_at'])
        _set_meal_stop_threshold(Decimal('0.00'))

    def test_phone_only_customer_can_get_wallet_and_recharge(self):
        wallet = self.client.get(self.wallet_url)
        self.assertEqual(wallet.status_code, 200)
        self.assertEqual(wallet.data['balance'], '0.00')

        response = self.client.post(
            self.recharge_url,
            {
                'amount': '100.00',
                'payment_method': 'bkash',
                'transaction_id': 'PHONE-TX-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['transaction']['status'], 'pending')
        self.assertEqual(response.data['transaction']['transaction_id'], 'PHONE-TX-1')

    def test_phone_only_customer_passes_withdraw_identity_gate(self):
        wallet = get_or_create_wallet(self.profile)
        credit_wallet(wallet, Decimal('200.00'))

        response = self.client.post(
            self.withdraw_url,
            {'amount': '50.00'},
            format='json',
        )
        # Identity must pass; expect pending withdraw (200), not identity 403.
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['transaction']['type'], 'withdraw')
        self.assertEqual(response.data['transaction']['status'], 'pending')

    def test_unverified_identity_denied_on_recharge_with_wallet_message(self):
        user, _profile = _make_unverified_customer()
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'UNVERIFIED-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        detail = str(response.data.get('detail', response.data))
        self.assertEqual(detail, IDENTITY_VERIFICATION_REQUIRED_WALLET_MESSAGE)
        self.assertNotIn('Email verification is required', detail)
        self.assertNotIn('placing an order', detail)
