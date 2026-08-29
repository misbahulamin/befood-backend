from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from user_management.models import AdminProfile, RiderProfile
from user_management.services.deliveryman_email import PENDING_APPROVAL_MESSAGE
from user_management.services.email_verification import generate_token, generate_uid


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://www.befood.com.bd',
    DELIVERYMAN_EMAIL_VERIFICATION_FRONTEND_PATH='/deliveryman/verify-email',
)
class DeliverymanAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('user_management:deliveryman-register')
        self.login_url = reverse('user_management:deliveryman-login')
        self.resend_url = reverse('user_management:deliveryman-resend-verification')
        self.me_url = reverse('user_management:deliveryman-me')
        self.list_url = reverse('user_management:admin-deliveryman-list')
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')

    def registration_payload(self, **overrides):
        payload = {
            'email': 'rider@example.com',
            'first_name': 'Karim',
            'last_name': 'Hossain',
            'phone': '1812345678',
            'address': 'House 10, Road 2, Dhaka',
            'password': 'StrongPassword123',
        }
        payload.update(overrides)
        return payload

    def register_deliveryman(self, **overrides):
        return self.client.post(self.register_url, self.registration_payload(**overrides), format='json')

    def verify_deliveryman(self, user):
        uid = generate_uid(user)
        token = generate_token(user)
        return self.client.get(
            reverse('user_management:deliveryman-verify-email', kwargs={'uidb64': uid, 'token': token})
        )

    def login_deliveryman(self, email='rider@example.com', password='StrongPassword123'):
        return self.client.post(self.login_url, {'email': email, 'password': password}, format='json')

    def create_admin_user(self, email='admin@example.com', password='StrongPassword123'):
        user = User.objects.create_user(
            username='admin-user',
            email=email,
            password=password,
            first_name='Admin',
            last_name='User',
            is_active=True,
        )
        AdminProfile.objects.create(user=user, is_verified=True)
        user.groups.add(self.admin_group)
        return user

    def admin_client(self):
        admin = self.create_admin_user()
        token = Token.objects.create(user=admin)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def test_registration_success_creates_inactive_user(self):
        response = self.register_deliveryman()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='rider@example.com')
        self.assertFalse(user.is_active)
        self.assertTrue(hasattr(user, 'rider_profile'))
        self.assertEqual(user.rider_profile.phone, '1812345678')
        self.assertEqual(user.rider_profile.approval_status, RiderProfile.ApprovalStatus.PENDING)
        self.assertFalse(user.rider_profile.is_verified)
        self.assertTrue(user.groups.filter(name='DELIVERY_MAN').exists())

    def test_registration_sends_verification_email(self):
        self.register_deliveryman()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Activate your Befood Delivery Man account', mail.outbox[0].subject)
        body = mail.outbox[0].body
        html = mail.outbox[0].alternatives[0][0]
        expected_prefix = 'https://www.befood.com.bd/deliveryman/verify-email/'
        self.assertIn(expected_prefix, body)
        self.assertIn(expected_prefix, html)
        self.assertNotIn('/user_management/deliveryman/verify-email/', body)
        self.assertNotIn('/user_management/deliveryman/verify-email/', html)

    def test_duplicate_email_is_blocked(self):
        self.register_deliveryman()
        response = self.register_deliveryman(phone='1999999999', email='rider@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)

    def test_duplicate_phone_is_blocked(self):
        self.register_deliveryman()
        response = self.register_deliveryman(email='other@example.com', phone='1812345678')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_email_verification_does_not_activate_login(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        response = self.verify_deliveryman(user)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        profile = user.rider_profile
        profile.refresh_from_db()
        self.assertTrue(profile.is_email_verified)
        self.assertFalse(user.is_active)
        self.assertFalse(profile.is_verified)
        login_response = self.login_deliveryman()
        self.assertEqual(login_response.status_code, 400)
        self.assertEqual(login_response.data['detail'], PENDING_APPROVAL_MESSAGE)

    def test_already_verified_email_link(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        response = self.verify_deliveryman(user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message'], 'Email is already verified.')

    def test_login_before_email_verification_is_blocked(self):
        self.register_deliveryman()
        response = self.login_deliveryman()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Please verify your email before login.')

    def test_pending_approval_blocks_login_with_message(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        response = self.login_deliveryman()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PENDING_APPROVAL_MESSAGE)
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_rejected_account_cannot_login(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        admin = self.admin_client()
        public_id = user.rider_profile.public_id
        reject_url = reverse(
            'user_management:admin-deliveryman-reject',
            kwargs={'public_id': public_id},
        )
        reject_response = admin.post(reject_url, {'reason': 'Incomplete documents'}, format='json')
        self.assertEqual(reject_response.status_code, 200)
        response = self.login_deliveryman()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], PENDING_APPROVAL_MESSAGE)

    def test_successful_login_after_approve(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        admin = self.admin_client()
        approve_url = reverse(
            'user_management:admin-deliveryman-approve',
            kwargs={'public_id': user.rider_profile.public_id},
        )
        mail.outbox.clear()
        approve_response = admin.post(approve_url, format='json')
        self.assertEqual(approve_response.status_code, 200)
        self.assertTrue(approve_response.data['is_verified'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('approved', mail.outbox[0].subject.lower())
        response = self.login_deliveryman()
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertTrue(response.data['rider_profile']['is_verified'])

    def test_admin_pending_queue_excludes_unverified_email(self):
        self.register_deliveryman()
        admin = self.admin_client()
        response = admin.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_admin_pending_queue_includes_email_verified(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        admin = self.admin_client()
        response = admin.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['email'], 'rider@example.com')

    def test_admin_detail_by_public_id(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        admin = self.admin_client()
        detail_url = reverse(
            'user_management:admin-deliveryman-detail',
            kwargs={'public_id': user.rider_profile.public_id},
        )
        response = admin.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['phone'], '1812345678')
        self.assertEqual(response.data['address'], 'House 10, Road 2, Dhaka')

    def test_non_admin_cannot_list_deliverymen(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        response = self.client.get(self.list_url)
        self.assertIn(response.status_code, (401, 403))

    def test_revoke_and_reapprove(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        admin = self.admin_client()
        public_id = user.rider_profile.public_id
        approve_url = reverse(
            'user_management:admin-deliveryman-approve',
            kwargs={'public_id': public_id},
        )
        status_url = reverse(
            'user_management:admin-deliveryman-verified-status',
            kwargs={'public_id': public_id},
        )
        admin.post(approve_url, format='json')
        revoke = admin.patch(status_url, {'is_verified': False}, format='json')
        self.assertEqual(revoke.status_code, 200)
        self.assertFalse(revoke.data['is_verified'])
        login_blocked = self.login_deliveryman()
        self.assertEqual(login_blocked.status_code, 400)
        reapprove = admin.patch(status_url, {'is_verified': True}, format='json')
        self.assertEqual(reapprove.status_code, 200)
        self.assertTrue(reapprove.data['is_verified'])
        login_ok = self.login_deliveryman()
        self.assertEqual(login_ok.status_code, 200)

    def test_me_requires_verified_deliveryman(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        self.verify_deliveryman(user)
        admin = self.admin_client()
        admin.post(
            reverse(
                'user_management:admin-deliveryman-approve',
                kwargs={'public_id': user.rider_profile.public_id},
            ),
            format='json',
        )
        login = self.login_deliveryman()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {login.data["token"]}')
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['email'], 'rider@example.com')

    def test_approve_before_email_verification_rejected(self):
        self.register_deliveryman()
        user = User.objects.get(email='rider@example.com')
        admin = self.admin_client()
        response = admin.post(
            reverse(
                'user_management:admin-deliveryman-approve',
                kwargs={'public_id': user.rider_profile.public_id},
            ),
            format='json',
        )
        self.assertEqual(response.status_code, 422)
