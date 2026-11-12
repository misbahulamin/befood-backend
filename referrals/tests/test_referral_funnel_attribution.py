"""Funnel attribution: pending intent, finalize skips, analytics uniqueness."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from meals.models import MealCategory
from orders.models import CustomerSubscription
from referrals.models import ReferralAttributionEvent, ReferralRelationship
from referrals.services.codes import ensure_referral_profile
from referrals.services.events import record_validation_event
from referrals.services.queries import admin_analytics
from user_management.models import AdminProfile, CustomerProfile, PendingCustomerRegistration, PhoneAuthOTP
from user_management.services.auth_otp import hash_otp_code
from user_management.services.pending_registration import issue_pending_otp


def _thumb():
    buf = BytesIO()
    Image.new('RGB', (8, 8), color='red').save(buf, format='JPEG')
    return SimpleUploadedFile('t.jpg', buf.getvalue(), content_type='image/jpeg')


def _referrer_with_active_sub(email='funnel_ref@ex.com', phone='1710000099'):
    user = User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='x',
    )
    Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(Group.objects.get(name='CUSTOMER'))
    profile = CustomerProfile.objects.create(
        user=user,
        phone=phone,
        is_email_verified=True,
        email_verified_at=timezone.now(),
    )
    ensure_referral_profile(profile)
    meal = MealCategory.objects.create(
        meal_name='Funnel Meal',
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
        meal_name_snapshot='Funnel Meal',
        meal_period_snapshot='lunch',
        status=CustomerSubscription.Status.ACTIVE,
        started_on=timezone.localdate(),
    )
    return profile


@override_settings(
    REFERRAL_ENABLED=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AUTH_OTP_RESEND_COOLDOWN_SECONDS=0,
)
class PendingReferralIntentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.referrer = _referrer_with_active_sub()
        self.code = self.referrer.referral_profile.code
        self.register_url = reverse('user_management:customer-register')

    def test_reregister_without_code_preserves_intent(self):
        first = self.client.post(
            self.register_url,
            {
                'email': 'preserve@ex.com',
                'password': 'StrongPassword123',
                'referral_code': self.code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(first.status_code, 201)
        pending = PendingCustomerRegistration.objects.get(email='preserve@ex.com')
        self.assertEqual(pending.referral_code, self.code)
        self.assertEqual(pending.referral_client_type, 'mobile')

        second = self.client.post(
            self.register_url,
            {'email': 'preserve@ex.com', 'password': 'AnotherStrongPass123'},
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(second.status_code, 201)
        pending.refresh_from_db()
        self.assertEqual(pending.referral_code, self.code)
        self.assertEqual(pending.referral_client_type, 'mobile')

    def test_reregister_with_new_code_replaces_intent(self):
        other = _referrer_with_active_sub(email='other_ref@ex.com', phone='1710000088')
        other_code = other.referral_profile.code
        self.client.post(
            self.register_url,
            {
                'email': 'replace@ex.com',
                'password': 'StrongPassword123',
                'referral_code': self.code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        res = self.client.post(
            self.register_url,
            {
                'email': 'replace@ex.com',
                'password': 'AnotherStrongPass123',
                'referral_code': other_code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(res.status_code, 201)
        pending = PendingCustomerRegistration.objects.get(email='replace@ex.com')
        self.assertEqual(pending.referral_code, other_code)


@override_settings(
    REFERRAL_ENABLED=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class FinalizeAttributionSkipTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.referrer = _referrer_with_active_sub(email='skip_ref@ex.com', phone='1710000077')
        self.code = self.referrer.referral_profile.code
        self.register_url = reverse('user_management:customer-register')
        self.verify_otp_url = reverse('user_management:verify-email-otp')

    def test_inactive_referrer_finalize_skips_with_reason(self):
        res = self.client.post(
            self.register_url,
            {
                'email': 'skipme@ex.com',
                'password': 'StrongPassword123',
                'referral_code': self.code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(res.status_code, 201)
        # Cancel referrer subscription before finalize.
        CustomerSubscription.objects.filter(customer=self.referrer).update(
            status=CustomerSubscription.Status.CANCELLED
        )
        pending = PendingCustomerRegistration.objects.get(email='skipme@ex.com')
        otp = issue_pending_otp(pending, force_new=True).plaintext_otp
        verify = self.client.post(
            self.verify_otp_url,
            {'email': 'skipme@ex.com', 'otp': otp},
            format='json',
        )
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(User.objects.filter(email__iexact='skipme@ex.com').exists())
        self.assertFalse(verify.data.get('referral_attributed'))
        self.assertEqual(verify.data.get('referral_status_reason'), 'REFERRER_INACTIVE')
        user = User.objects.get(email__iexact='skipme@ex.com')
        self.assertFalse(ReferralRelationship.objects.filter(referred=user.customer_profile).exists())
        skip = ReferralAttributionEvent.objects.get(
            customer=user.customer_profile,
            outcome=ReferralAttributionEvent.Outcome.SKIPPED,
        )
        self.assertEqual(skip.error_code, 'REFERRER_INACTIVE')
        self.assertEqual(skip.stage, ReferralAttributionEvent.Stage.FINALIZE)


@override_settings(REFERRAL_ENABLED=True, REFERRAL_COMMISSION_PERCENT='5')
class FunnelAnalyticsTests(TestCase):
    def setUp(self):
        self.referrer = _referrer_with_active_sub(email='analytics_ref@ex.com', phone='1710000066')
        self.code = self.referrer.referral_profile.code

    def test_ten_validates_one_unique_code_no_registrations(self):
        for _ in range(10):
            record_validation_event(
                code=self.code,
                is_valid=True,
                reason='OK',
                referrer=self.referrer,
            )
        data = admin_analytics()
        self.assertEqual(data['total_successful_validations'], 10)
        self.assertEqual(data['unique_successful_validation_codes'], 1)
        self.assertEqual(data['total_successful_registrations'], 0)

    def test_admin_analytics_api_exposes_additive_fields(self):
        admin = User.objects.create_user(username='fadmin', email='fadmin@ex.com', password='x')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        admin.groups.add(admin_group)
        AdminProfile.objects.create(user=admin, is_verified=True)
        token = Token.objects.create(user=admin)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        record_validation_event(code=self.code, is_valid=True, reason='OK', referrer=self.referrer)
        res = client.get('/api/v1/web/referrals/analytics/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('unique_successful_validation_codes', res.data)
        self.assertIn('attribution_rate_vs_unique_ok', res.data)
        self.assertIn('attribution_skips_by_reason', res.data)
        self.assertEqual(res.data['unique_successful_validation_codes'], 1)


@override_settings(REFERRAL_ENABLED=True, REFERRAL_COMMISSION_PERCENT='5')
class PhoneReferralEnvelopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.referrer = _referrer_with_active_sub(email='phone_env@ex.com', phone='1710000055')
        self.code = self.referrer.referral_profile.code

    def test_new_phone_includes_referral_attributed_true(self):
        now = timezone.now()
        PhoneAuthOTP.objects.create(
            phone='1788889999',
            code_hash=hash_otp_code('123456'),
            expires_at=now + timedelta(minutes=10),
            max_attempts=5,
        )
        res = self.client.post(
            '/user_management/phone/otp/verify/',
            {
                'phone': '01788889999',
                'otp': '123456',
                'referral_code': self.code,
            },
            format='json',
            HTTP_X_CLIENT_TYPE='mobile',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('referral_attributed'))
        self.assertIsNone(res.data.get('referral_status_reason'))
        profile = CustomerProfile.objects.get(phone='1788889999')
        self.assertTrue(ReferralRelationship.objects.filter(referred=profile).exists())
