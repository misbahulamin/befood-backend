"""Customer identity linking: email/phone same account, referral once, bind guards."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from meals.models import MealCategory
from orders.models import CustomerSubscription
from referrals.models import ReferralRelationship
from referrals.services.attribution import attribute_on_signup
from referrals.services.codes import ensure_referral_profile
from referrals.services.eligibility import ReferralError
from user_management.models import CustomerProfile, PhoneAuthOTP
from user_management.services.auth_otp import hash_otp_code
from user_management.services.auth_session import issue_auth_session
from user_management.services.customer_factory import create_phone_only_customer
from user_management.services.identity_resolve import (
    find_customer_by_email,
    find_customer_by_phone,
    resolve_customer,
)
from user_management.services.phone_otp import verify_phone_otp
from wallet.services.ledger import credit_wallet, get_or_create_wallet
from wallet.models import WalletTransaction


def _thumb():
    buf = BytesIO()
    Image.new('RGB', (8, 8), color='red').save(buf, format='JPEG')
    return SimpleUploadedFile('t.jpg', buf.getvalue(), content_type='image/jpeg')


def _make_verified_email_customer(email='customer@example.com', password='TestPass123!', phone=None):
    user = User.objects.create_user(
        username=email.split('@')[0] + email.split('@')[1][:3],
        email=email,
        password=password,
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    CustomerProfile.objects.create(
        user=user,
        phone=phone,
        is_email_verified=True,
        email_verified_at=timezone.now(),
        is_phone_verified=bool(phone),
        phone_verified_at=timezone.now() if phone else None,
    )
    return user


def _referrer_with_code():
    user = _make_verified_email_customer('referrer@example.com', phone='1710000001')
    profile = user.customer_profile
    ensure_referral_profile(profile)
    meal = MealCategory.objects.create(
        meal_name='Ref Meal',
        total_price=Decimal('100.00'),
        meal_thumbnail=_thumb(),
        meal_type=MealCategory.MealType.MONTHLY,
        meal_period=MealCategory.MealPeriod.LUNCH,
        is_active=True,
        is_subscribable=True,
    )
    CustomerSubscription.objects.create(
        customer=profile,
        meal=meal,
        meal_name_snapshot='Ref Meal',
        meal_period_snapshot='lunch',
        status=CustomerSubscription.Status.ACTIVE,
        started_on=timezone.localdate(),
    )
    return profile


def _seed_otp(phone: str, code: str = '123456') -> None:
    now = timezone.now()
    PhoneAuthOTP.objects.create(
        phone=phone,
        code_hash=hash_otp_code(code),
        expires_at=now + timedelta(minutes=10),
        max_attempts=5,
    )


@override_settings(REFERRAL_ENABLED=True, REFERRAL_COMMISSION_PERCENT='5')
class IdentityResolveHelperTests(TestCase):
    def test_resolve_by_email_and_phone(self):
        user = _make_verified_email_customer('a@example.com', phone='1711111111')
        self.assertEqual(find_customer_by_email('A@Example.com').pk, user.customer_profile.pk)
        self.assertEqual(find_customer_by_phone('01711111111').pk, user.customer_profile.pk)
        self.assertEqual(
            resolve_customer(email='a@example.com', phone='1711111111').pk,
            user.customer_profile.pk,
        )


@override_settings(
    REFERRAL_ENABLED=True,
    REFERRAL_COMMISSION_PERCENT='5',
    SMS_NET_BD_API_KEY='test-key',
    SMS_NET_BD_SEND_SMS_URL='https://sms.test/send',
)
class EmailThenPhoneSameAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.referrer = _referrer_with_code()
        self.code = self.referrer.referral_profile.code

    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_email_referral_then_bind_phone_same_account(self, mock_send):
        mock_send.return_value = {'error': 0}
        user = _make_verified_email_customer('newbie@example.com')
        ensure_referral_profile(user.customer_profile)
        attribute_on_signup(
            referred_customer=user.customer_profile,
            referral_code=self.code,
            client_type='mobile',
        )
        self.assertEqual(ReferralRelationship.objects.filter(referred=user.customer_profile).count(), 1)

        session = issue_auth_session(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {session.key}')
        user_count = User.objects.count()

        send = self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01722223333'},
            format='json',
        )
        self.assertEqual(send.status_code, status.HTTP_200_OK)
        otp = PhoneAuthOTP.objects.filter(phone='1722223333').latest('created_at')
        otp.code_hash = hash_otp_code('123456')
        otp.save(update_fields=['code_hash'])

        bind = self.client.post(
            '/user_management/phone/otp/bind/verify/',
            {'phone': '01722223333', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(bind.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), user_count)
        user.customer_profile.refresh_from_db()
        self.assertEqual(user.customer_profile.phone, '1722223333')
        self.assertEqual(ReferralRelationship.objects.filter(referred=user.customer_profile).count(), 1)

        self.client.credentials()
        _seed_otp('1722223333')
        login = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '01722223333', 'otp': '123456'},
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(login.data['user']['id'], user.id)


@override_settings(
    REFERRAL_ENABLED=True,
    REFERRAL_COMMISSION_PERCENT='5',
    SMS_NET_BD_API_KEY='test-key',
    SMS_NET_BD_SEND_SMS_URL='https://sms.test/send',
)
class PhoneThenEmailSameAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.referrer = _referrer_with_code()
        self.code = self.referrer.referral_profile.code

    def test_phone_referral_then_set_email_same_account(self):
        user, profile = create_phone_only_customer('1733334444')
        attribute_on_signup(
            referred_customer=profile,
            referral_code=self.code,
            client_type='mobile',
        )
        session = issue_auth_session(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {session.key}')
        response = self.client.post(
            '/user_management/customer/profile/email/',
            {'email': 'phonefirst@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.email, 'phonefirst@example.com')
        self.assertEqual(CustomerProfile.objects.filter(pk=profile.pk).count(), 1)
        self.assertEqual(ReferralRelationship.objects.filter(referred=profile).count(), 1)


@override_settings(REFERRAL_ENABLED=True, REFERRAL_COMMISSION_PERCENT='5')
class ReferralOnceTests(TestCase):
    def setUp(self):
        self.referrer = _referrer_with_code()
        self.code = self.referrer.referral_profile.code
        self.client = APIClient()

    def test_existing_phone_login_ignores_referral(self):
        user, profile = create_phone_only_customer('1744445555')
        attribute_on_signup(
            referred_customer=profile,
            referral_code=self.code,
            client_type='mobile',
        )
        before = ReferralRelationship.objects.get(referred=profile)
        _seed_otp('1744445555')
        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {
                'phone': '01744445555',
                'otp': '123456',
                'referral_code': self.code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ReferralRelationship.objects.filter(referred=profile).count(), 1)
        before.refresh_from_db()
        self.assertEqual(before.referrer_id, self.referrer.pk)

    def test_new_phone_accepts_referral(self):
        _seed_otp('1755556666')
        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {
                'phone': '01755556666',
                'otp': '123456',
                'referral_code': self.code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = CustomerProfile.objects.get(phone='1755556666')
        self.assertTrue(ReferralRelationship.objects.filter(referred=profile).exists())

    def test_second_attribution_rejected(self):
        user, profile = create_phone_only_customer('1766667777')
        attribute_on_signup(
            referred_customer=profile,
            referral_code=self.code,
            client_type='mobile',
        )
        with self.assertRaises(ReferralError) as ctx:
            attribute_on_signup(
                referred_customer=profile,
                referral_code=self.code,
                client_type='mobile',
            )
        self.assertEqual(ctx.exception.code, 'REFERRAL_ALREADY_ATTRIBUTED')


@override_settings(
    SMS_NET_BD_API_KEY='test-key',
    SMS_NET_BD_SEND_SMS_URL='https://sms.test/send',
)
class AuthenticatedAnonymousVerifyGuardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _make_verified_email_customer('guard@example.com')
        self.session = issue_auth_session(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session.key}')

    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_authenticated_anonymous_verify_binds_not_creates(self, mock_send):
        mock_send.return_value = {'error': 0}
        user_count = User.objects.count()
        _seed_otp('1777778888')
        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '01777778888', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), user_count)
        self.user.customer_profile.refresh_from_db()
        self.assertEqual(self.user.customer_profile.phone, '1777778888')
        self.assertFalse(
            ReferralRelationship.objects.filter(referred=self.user.customer_profile).exists()
        )

    def test_service_authenticated_user_binds(self):
        _seed_otp('1788889999')
        user_count = User.objects.count()
        verify_phone_otp(
            '01788889999',
            '123456',
            authenticated_user=self.user,
        )
        self.assertEqual(User.objects.count(), user_count)
        self.user.customer_profile.refresh_from_db()
        self.assertEqual(self.user.customer_profile.phone, '1788889999')


@override_settings(
    SMS_NET_BD_API_KEY='test-key',
    SMS_NET_BD_SEND_SMS_URL='https://sms.test/send',
)
class BindConflictAndWalletContinuityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _make_verified_email_customer('wallet@example.com')
        wallet = get_or_create_wallet(self.user.customer_profile)
        credit_wallet(wallet, Decimal('50.00'), type=WalletTransaction.Type.RECHARGE)
        meal = MealCategory.objects.create(
            meal_name='Sub Meal',
            total_price=Decimal('100.00'),
            meal_thumbnail=_thumb(),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
            is_subscribable=True,
        )
        CustomerSubscription.objects.create(
            customer=self.user.customer_profile,
            meal=meal,
            meal_name_snapshot='Sub Meal',
            meal_period_snapshot='lunch',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=timezone.localdate(),
        )
        self.session = issue_auth_session(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.session.key}')

    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_bind_then_phone_login_keeps_wallet_and_subscription(self, mock_send):
        mock_send.return_value = {'error': 0}
        send = self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01712121212'},
            format='json',
        )
        self.assertEqual(send.status_code, status.HTTP_200_OK)
        otp = PhoneAuthOTP.objects.filter(phone='1712121212').latest('created_at')
        otp.code_hash = hash_otp_code('123456')
        otp.save(update_fields=['code_hash'])
        bind = self.client.post(
            '/user_management/phone/otp/bind/verify/',
            {'phone': '01712121212', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(bind.status_code, status.HTTP_200_OK)

        self.client.credentials()
        _seed_otp('1712121212')
        login = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '01712121212', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(login.data['user']['id'], self.user.id)
        wallet = get_or_create_wallet(self.user.customer_profile)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('50.00'))
        self.assertTrue(
            CustomerSubscription.objects.filter(
                customer=self.user.customer_profile,
                status=CustomerSubscription.Status.ACTIVE,
            ).exists()
        )

    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_bind_conflict(self, mock_send):
        mock_send.return_value = {'error': 0}
        create_phone_only_customer('1799990000')
        send = self.client.post(
            '/user_management/phone/otp/bind/send/',
            {'phone': '01799990000'},
            format='json',
        )
        self.assertEqual(send.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(send.data['code'], 'PHONE_CONFLICT')


class ReferralInputAllowedSignalTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_email_check_referral_flags(self):
        _make_verified_email_customer('exists@example.com')
        exists = self.client.post(
            '/user_management/customer/email-check/',
            {'email': 'exists@example.com'},
            format='json',
        )
        self.assertFalse(exists.data['referral_input_allowed'])
        available = self.client.post(
            '/user_management/customer/email-check/',
            {'email': 'brandnew@example.com'},
            format='json',
        )
        self.assertTrue(available.data['referral_input_allowed'])

    def test_phone_availability_referral_flags(self):
        create_phone_only_customer('1701010101')
        existing = self.client.post(
            '/user_management/phone/check-availability/',
            {'phone': '01701010101', 'context': 'login'},
            format='json',
        )
        self.assertTrue(existing.data['phone_exists'])
        self.assertFalse(existing.data['referral_input_allowed'])
        fresh = self.client.post(
            '/user_management/phone/check-availability/',
            {'phone': '01702020202', 'context': 'login'},
            format='json',
        )
        self.assertFalse(fresh.data['phone_exists'])
        self.assertTrue(fresh.data['referral_input_allowed'])


class ReportIdentityCommandTests(TestCase):
    def test_command_runs_read_only(self):
        _make_verified_email_customer('report@example.com')
        create_phone_only_customer('1713131313')
        call_command('report_customer_identity_issues', limit=10)
