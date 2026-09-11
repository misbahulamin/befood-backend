"""OR identity rule: email-only or phone-only unlocks /me + gated features."""

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


def _set_meal_stop_threshold(amount: Decimal) -> None:
    settings_obj = OrderWalletSettings.load()
    settings_obj.meal_stop_threshold = amount
    settings_obj.save(update_fields=['meal_stop_threshold', 'updated_at'])


def _make_email_only_customer(username='email_only', email='email_only@example.com'):
    user = User.objects.create_user(
        username=username,
        email=email,
        password='StrongPassword123',
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    profile = CustomerProfile.objects.create(
        user=user,
        phone=None,
        is_email_verified=True,
        is_phone_verified=False,
        occupation=CustomerProfile.Occupation.STUDENT,
        is_bachelor=True,
    )
    return user, profile


def _make_phone_only_customer(username='phone_only', phone='1717777001'):
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


def _make_unverified_customer(username='unverif', phone='1717777002'):
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
class IdentityVerificationOrRuleAPITests(APITestCase):
    def setUp(self):
        platform = get_or_create_platform_wallet()
        platform.balance = Decimal('5000.00')
        platform.save(update_fields=['balance', 'updated_at'])
        _set_meal_stop_threshold(Decimal('0.00'))
        self.me_url = '/user_management/me/'
        self.profile_url = '/user_management/customer/profile/'
        self.recharge_url = reverse('wallet:wallet-recharge')

    def _auth(self, user):
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_me_email_only_identity_true_phone_soft_required(self):
        user, _ = _make_email_only_customer()
        self._auth(user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['phone_verification_required'])
        vs = response.data['verification_status']
        self.assertTrue(vs['identity_verified'])
        self.assertTrue(vs['email_verified'])
        self.assertFalse(vs['phone_verified'])

    def test_me_phone_only_identity_true(self):
        user, _ = _make_phone_only_customer()
        self._auth(user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['phone_verification_required'])
        vs = response.data['verification_status']
        self.assertTrue(vs['identity_verified'])
        self.assertTrue(vs['phone_verified'])
        self.assertFalse(vs['email_verified'])

    def test_profile_includes_verification_status(self):
        user, _ = _make_email_only_customer(username='prof_email', email='prof_email@example.com')
        self._auth(user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('verification_status', response.data)
        self.assertTrue(response.data['verification_status']['identity_verified'])
        self.assertTrue(response.data['phone_verification_required'])

    def test_email_only_can_recharge_past_identity_gate(self):
        user, _ = _make_email_only_customer(username='recharge_email', email='recharge_email@example.com')
        self._auth(user)
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '50.00',
                'payment_method': 'bkash',
                'transaction_id': 'EMAIL-OR-TX-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['transaction']['status'], 'pending')

    def test_phone_only_can_recharge_past_identity_gate(self):
        user, _ = _make_phone_only_customer(username='recharge_phone', phone='1717777003')
        self._auth(user)
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '50.00',
                'payment_method': 'nagad',
                'transaction_id': 'PHONE-OR-TX-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['transaction']['status'], 'pending')

    def test_unverified_denied_on_recharge(self):
        user, _ = _make_unverified_customer()
        self._auth(user)
        response = self.client.post(
            self.recharge_url,
            {
                'amount': '10.00',
                'payment_method': 'bkash',
                'transaction_id': 'UNVER-OR-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        detail = str(response.data.get('detail', response.data))
        self.assertEqual(detail, IDENTITY_VERIFICATION_REQUIRED_WALLET_MESSAGE)
        self.assertNotIn('Email verification is required', detail)
