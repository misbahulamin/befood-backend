"""Referral API smoke tests."""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from orders.models import CustomerSubscription
from referrals.services.codes import ensure_referral_profile
from user_management.models import AdminProfile, CustomerProfile


def _customer(username: str) -> tuple[CustomerProfile, str]:
    user = User.objects.create_user(
        username=username, email=f'{username}@ex.com', password='x'
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    profile = CustomerProfile.objects.create(user=user)
    ensure_referral_profile(profile)
    token = Token.objects.create(user=user)
    return profile, token.key


@override_settings(REFERRAL_ENABLED=True)
class ReferralApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.profile, self.token = _customer('api_ref')

    def test_me_requires_auth(self):
        res = self.client.get('/referrals/me/')
        self.assertIn(res.status_code, (401, 403))

    def test_me_ok(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        res = self.client.get('/referrals/me/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('code', res.data)
        self.assertTrue(str(res.data['code']).startswith('BEF'))

    def test_validate_invalid_code(self):
        res = self.client.post(
            '/referrals/validate/',
            {'referral_code': 'BEFINVALID'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_admin_analytics_denied_for_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        res = self.client.get('/api/v1/web/referrals/analytics/')
        self.assertIn(res.status_code, (401, 403))

    def test_admin_analytics_ok(self):
        admin = User.objects.create_user(
            username='radmin', email='radmin@ex.com', password='x'
        )
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        admin.groups.add(admin_group)
        AdminProfile.objects.create(user=admin, is_verified=True)
        token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        res = self.client.get('/api/v1/web/referrals/analytics/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_relationships', res.data)

    def test_commissions_list_exposes_status_reason(self):
        from decimal import Decimal
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from admin_wallet.models import AdminWallet, AdminWalletTransaction
        from admin_wallet.services.ledger import credit_admin_wallet
        from meals.models import MealCategory
        from orders.models import OrderDelivery
        from referrals.services.attribution import attribute_on_signup
        from referrals.services.commission import credit_referral_commission_for_delivery

        referred, _referred_token = _customer('api_ree')
        meal_buf = BytesIO()
        Image.new('RGB', (8, 8), color='red').save(meal_buf, format='JPEG')
        meal = MealCategory.objects.create(
            meal_name='Api Meal',
            total_price=Decimal('100.00'),
            meal_thumbnail=SimpleUploadedFile(
                't.jpg', meal_buf.getvalue(), content_type='image/jpeg'
            ),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
            is_subscribable=True,
        )
        for customer in (self.profile, referred):
            CustomerSubscription.objects.create(
                customer=customer,
                meal=meal,
                meal_name_snapshot='Api Meal',
                meal_period_snapshot='lunch',
                status=CustomerSubscription.Status.ACTIVE,
                started_on=timezone.localdate(),
            )
        attribute_on_signup(
            referred_customer=referred,
            referral_code=self.profile.referral_profile.code,
            client_type='mobile',
        )
        AdminWallet.objects.get_or_create(
            code=AdminWallet.PLATFORM_CODE,
            defaults={'balance': Decimal('0.00')},
        )
        credit_admin_wallet(
            Decimal('50.00'),
            type=AdminWalletTransaction.Type.MANUAL_DEPOSIT,
            note='api float',
        )
        referred_sub = CustomerSubscription.objects.get(customer=referred)
        delivery = OrderDelivery.objects.create(
            subscription=referred_sub,
            service_date=timezone.localdate(),
            meal_period='lunch',
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            payment_status=OrderDelivery.PaymentStatus.CHARGED,
            charged_amount=Decimal('100.00'),
        )
        row = credit_referral_commission_for_delivery(delivery)
        self.assertEqual(row.status_reason, 'REFERRER_MEAL_NOT_CONSUMED')

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')
        res = self.client.get('/referrals/me/commissions/')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        self.assertTrue(results)
        self.assertIn('status', results[0])
        self.assertIn('status_reason', results[0])
        self.assertEqual(results[0]['status_reason'], 'REFERRER_MEAL_NOT_CONSUMED')


@override_settings(REFERRAL_ENABLED=True, REFERRAL_COMMISSION_PERCENT='5')
class ReferralProgramSettingsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer, self.customer_token = _customer('settings_cust')
        admin = User.objects.create_user(
            username='settings_admin', email='settings_admin@ex.com', password='x'
        )
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        admin.groups.add(admin_group)
        AdminProfile.objects.create(user=admin, is_verified=True)
        self.admin_token = Token.objects.create(user=admin).key

    def test_settings_denied_for_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token}')
        res = self.client.get('/api/v1/web/referrals/settings/')
        self.assertIn(res.status_code, (401, 403))

    def test_settings_get_and_patch(self):
        from referrals.models import ReferralProgramSettings

        ReferralProgramSettings.load()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        res = self.client.get('/api/v1/web/referrals/settings/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('referral_commission_percent', res.data)

        res = self.client.patch(
            '/api/v1/web/referrals/settings/',
            {'referral_commission_percent': '10.00'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(str(res.data['referral_commission_percent']), '10.00')
        self.assertEqual(
            ReferralProgramSettings.load().commission_percent,
            Decimal('10.00'),
        )

    def test_settings_rejects_invalid_percent(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token}')
        before = self.client.get('/api/v1/web/referrals/settings/').data[
            'referral_commission_percent'
        ]
        for bad in ('150', '-5', '10.123'):
            res = self.client.patch(
                '/api/v1/web/referrals/settings/',
                {'referral_commission_percent': bad},
                format='json',
            )
            self.assertEqual(res.status_code, 400, msg=bad)
        after = self.client.get('/api/v1/web/referrals/settings/').data[
            'referral_commission_percent'
        ]
        self.assertEqual(after, before)