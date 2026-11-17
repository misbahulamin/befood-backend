"""Product profile completeness signal and auth/me demographics parity."""

from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch

from user_management.models import CustomerProfile, PhoneAuthOTP
from user_management.services.auth_otp import hash_otp_code
from user_management.services.auth_session import (
    build_customer_auth_response,
    build_customer_profile_session_dict,
)
from user_management.services.profile_onboarding import get_product_profile_completion


class ProductProfileCompletionHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='prodcomplete',
            email='prodcomplete@example.com',
            password='StrongPassword123',
            first_name='Rahim',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712345601',
            gender='male',
            birth_date=date(2000, 5, 15),
            profile_completed=False,
        )

    def test_complete_demographics(self):
        result = get_product_profile_completion(self.user, self.profile)
        self.assertTrue(result['completed'])
        self.assertEqual(result['missing_fields'], [])

    def test_missing_email_still_complete_for_phone_first(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])
        result = get_product_profile_completion(self.user, self.profile)
        self.assertTrue(result['completed'])
        self.assertNotIn('email', result['missing_fields'])

    def test_missing_birth_date(self):
        self.profile.birth_date = None
        self.profile.save(update_fields=['birth_date'])
        result = get_product_profile_completion(self.user, self.profile)
        self.assertFalse(result['completed'])
        self.assertEqual(result['missing_fields'], ['birth_date'])

    def test_missing_gender(self):
        self.profile.gender = None
        self.profile.save(update_fields=['gender'])
        result = get_product_profile_completion(self.user, self.profile)
        self.assertFalse(result['completed'])
        self.assertEqual(result['missing_fields'], ['gender'])

    def test_extended_profile_completed_false_is_irrelevant(self):
        self.profile.profile_completed = False
        self.profile.save(update_fields=['profile_completed'])
        result = get_product_profile_completion(self.user, self.profile)
        self.assertTrue(result['completed'])
        self.assertFalse(self.profile.profile_completed)


class AuthMeDemographicsParityTests(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='parityuser',
            email='parity@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            last_name='Uddin',
        )
        self.user.groups.add(Group.objects.get(name='CUSTOMER'))
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712345602',
            is_phone_verified=True,
            phone_verified_at=timezone.now(),
            gender='female',
            birth_date=date(1998, 3, 20),
            profile_completed=False,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_session_dict_includes_gender_and_birth_date(self):
        payload = build_customer_profile_session_dict(self.profile)
        self.assertEqual(payload['gender'], 'female')
        self.assertEqual(payload['birth_date'], '1998-03-20')

    def test_auth_envelope_and_me_share_demographics(self):
        auth = build_customer_auth_response(self.user, auth_provider='phone')
        me = self.client.get('/user_management/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)

        for source in (auth['customer_profile'], me.data['customer_profile']):
            self.assertEqual(source['gender'], 'female')
            self.assertEqual(source['birth_date'], '1998-03-20')

        self.assertIn('product_profile_completion', auth)
        self.assertIn('product_profile_completion', me.data)
        self.assertTrue(auth['product_profile_completion']['completed'])
        self.assertTrue(me.data['product_profile_completion']['completed'])
        # Existing keys preserved.
        self.assertIn('onboarding_completion', auth)
        self.assertIn('profile_completed', auth['customer_profile'])
        self.assertFalse(auth['customer_profile']['profile_completed'])

    def test_unset_demographics_are_null(self):
        self.profile.gender = None
        self.profile.birth_date = None
        self.profile.save(update_fields=['gender', 'birth_date'])
        auth = build_customer_auth_response(self.user, auth_provider='email')
        self.assertIsNone(auth['customer_profile']['gender'])
        self.assertIsNone(auth['customer_profile']['birth_date'])
        self.assertFalse(auth['product_profile_completion']['completed'])
        self.assertEqual(
            set(auth['product_profile_completion']['missing_fields']),
            {'birth_date', 'gender'},
        )


class PhoneOtpProductCompletionEnvelopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.user = User.objects.create_user(
            username='otpcomplete',
            email='otpcomplete@example.com',
            password='StrongPassword123',
            first_name='Nila',
        )
        self.user.groups.add(Group.objects.get(name='CUSTOMER'))
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1712345603',
            is_phone_verified=True,
            phone_verified_at=timezone.now(),
            gender='other',
            birth_date=date(2001, 1, 1),
        )

    @override_settings(SMS_NET_BD_API_KEY='test-key', SMS_NET_BD_SEND_SMS_URL='https://sms.test/send')
    @patch('user_management.services.phone_otp.send_otp_sms')
    def test_otp_verify_includes_gender_birth_date_and_product_signal(self, mock_send):
        mock_send.return_value = {'error': 0}
        self.client.post(
            '/user_management/phone/otp/send/',
            {'phone': '01712345603'},
            format='json',
        )
        otp = PhoneAuthOTP.objects.filter(phone='1712345603').latest('created_at')
        otp.code_hash = hash_otp_code('123456')
        otp.save(update_fields=['code_hash'])

        response = self.client.post(
            '/user_management/phone/otp/verify/',
            {'phone': '01712345603', 'otp': '123456'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['customer_profile']['gender'], 'other')
        self.assertEqual(response.data['customer_profile']['birth_date'], '2001-01-01')
        self.assertTrue(response.data['product_profile_completion']['completed'])
        self.assertEqual(response.data['product_profile_completion']['missing_fields'], [])
