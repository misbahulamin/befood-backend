from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from user_management.models import CustomerProfile
from user_management.services.email_branding import build_greeting
from user_management.services.email_verification import generate_uid, send_activation_email
from user_management.services.password_reset import (
    PASSWORD_RESET_REQUEST_MESSAGE,
    generate_password_reset_token,
    send_password_reset_email,
)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_LOGO_URL=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/'
        'logo/befood_logo_for_template.png'
    ),
    EMAIL_FACEBOOK_ICON_URL=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/logo/icon-facebook.png'
    ),
    EMAIL_INSTAGRAM_ICON_URL=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/logo/icon-instagram.png'
    ),
    EMAIL_WHATSAPP_ICON_URL=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/logo/icon-whatsapp.png'
    ),
    EMAIL_PLAY_STORE_URL='https://play.google.com/store/apps/details?id=bd.com.befood',
    FRONTEND_URL='https://www.befood.com.bd',
    PASSWORD_RESET_FRONTEND_PATH='/reset-password',
    EMAIL_VERIFICATION_FRONTEND_PATH='/verify-email',
    DELIVERYMAN_EMAIL_VERIFICATION_FRONTEND_PATH='/deliveryman/verify-email',
)
class BrandedAuthEmailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Group.objects.get_or_create(name='CUSTOMER')
        self.factory = RequestFactory()
        self.password_reset_url = reverse('user_management:password-reset-request')

    def _make_customer(self, *, email='customer@example.com', first_name='Rahim', gender=None):
        user = User.objects.create_user(
            username=email,
            email=email,
            password='StrongPassword123',
            first_name=first_name,
            is_active=False,
        )
        profile = CustomerProfile.objects.create(user=user, gender=gender)
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        return user, profile

    def test_greeting_male_with_name(self):
        user, profile = self._make_customer(first_name='Rahim', gender='male')
        self.assertEqual(build_greeting(user, profile), 'Hello Rahim bhaiya')

    def test_greeting_female_with_name(self):
        user, profile = self._make_customer(
            email='female@example.com',
            first_name='Ayesha',
            gender='female',
        )
        self.assertEqual(build_greeting(user, profile), 'Hello Ayesha apu')

    def test_greeting_unknown_gender_without_name(self):
        user, profile = self._make_customer(
            email='unknown@example.com',
            first_name='',
            gender=None,
        )
        self.assertEqual(build_greeting(user, profile), 'Hello bhaiya/apu')

    def test_greeting_unknown_gender_with_name(self):
        user, profile = self._make_customer(
            email='named@example.com',
            first_name='Karim',
            gender=None,
        )
        self.assertEqual(build_greeting(user, profile), 'Hello Karim bhaiya/apu')

    def test_activation_email_html_is_branded_without_otp_boxes(self):
        user, _ = self._make_customer()
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'api.example.test'
        send_activation_email(request, user)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('Welcome to Befood', message.subject)
        html = message.alternatives[0][0]
        self.assertIn(
            'https://befood-media-storage.s3.ap-south-1.amazonaws.com/'
            'logo/befood_logo_for_template.png',
            html,
        )
        self.assertIn('Verify Email Address', html)
        self.assertIn('play.google.com/store/apps/details?id=bd.com.befood', html)
        self.assertIn('alt="Befood"', html)
        self.assertIn('icon-facebook.png', html)
        self.assertIn('icon-instagram.png', html)
        self.assertIn('icon-whatsapp.png', html)
        self.assertNotIn('Your verification code', html)
        self.assertNotIn('verification-code', html.lower())
        self.assertNotIn('Best Regards', html)
        self.assertNotIn('The Befood Team', html)
        self.assertNotIn('background-color:#FFD100', html)
        self.assertNotIn("background-color:{{ brand_yellow }}", html)

    def test_activation_email_uses_frontend_url_not_request_host(self):
        user, _ = self._make_customer(email='linkcheck@example.com')
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'api.example.test'
        send_activation_email(request, user)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        html = mail.outbox[0].alternatives[0][0]
        expected_prefix = 'https://www.befood.com.bd/verify-email/'
        self.assertIn(expected_prefix, body)
        self.assertIn(expected_prefix, html)
        self.assertNotIn('api.example.test', body)
        self.assertNotIn('api.example.test', html)
        self.assertNotIn('/user_management/verify-email/', body)
        self.assertNotIn('/user_management/verify-email/', html)

    def test_password_reset_request_sends_mail_for_existing_customer(self):
        user, _ = self._make_customer(email='reset@example.com')
        response = self.client.post(
            self.password_reset_url,
            {'email': 'reset@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], PASSWORD_RESET_REQUEST_MESSAGE)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Reset Password', html)
        self.assertIn('/reset-password?uid=', mail.outbox[0].body)
        self.assertIn('token=', mail.outbox[0].body)

    def test_password_reset_request_unknown_email_is_anti_enumeration(self):
        response = self.client.post(
            self.password_reset_url,
            {'email': 'missing@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], PASSWORD_RESET_REQUEST_MESSAGE)
        self.assertEqual(len(mail.outbox), 0)

    def test_activation_verify_rejects_password_reset_token(self):
        user, profile = self._make_customer(email='tokenmix@example.com')
        uid = generate_uid(user)
        reset_token = generate_password_reset_token(user)
        response = self.client.get(
            reverse(
                'user_management:verify-email',
                kwargs={'uidb64': uid, 'token': reset_token},
            )
        )
        self.assertEqual(response.status_code, 400)
        profile.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(profile.is_email_verified)
        self.assertFalse(user.is_active)

    def test_send_password_reset_email_includes_frontend_link(self):
        user, _ = self._make_customer(email='link@example.com', first_name='Nila', gender='female')
        send_password_reset_email(user)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('Hello Nila apu', body)
        self.assertIn('https://www.befood.com.bd/reset-password?uid=', body)
