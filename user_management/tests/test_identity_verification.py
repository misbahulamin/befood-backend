"""Unit tests for unified customer identity verification."""

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase
from django.utils import timezone

from user_management.models import CustomerProfile, SocialIdentity
from user_management.services.customer_factory import create_phone_only_customer
from user_management.services.identity_verification import (
    build_verification_status,
    is_customer_identity_verified,
    safe_user_email,
)


class IdentityVerificationHelperTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='CUSTOMER')

    def test_anonymous_not_verified(self):
        self.assertFalse(is_customer_identity_verified(AnonymousUser()))
        self.assertFalse(is_customer_identity_verified(None))

    def test_email_only_verified(self):
        user = User.objects.create_user(
            username='email_ok',
            email='email_ok@example.com',
            password='StrongPassword123',
        )
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        CustomerProfile.objects.create(
            user=user,
            is_email_verified=True,
            email_verified_at=timezone.now(),
        )
        self.assertTrue(is_customer_identity_verified(user))
        status = build_verification_status(user)
        self.assertTrue(status['email_verified'])
        self.assertTrue(status['identity_verified'])
        self.assertFalse(status['phone_verified'])
        self.assertFalse(status['google_verified'])
        self.assertFalse(status['facebook_verified'])

    def test_phone_only_verified(self):
        user, _profile = create_phone_only_customer('1712000001')
        self.assertEqual(safe_user_email(user), '')
        self.assertTrue(is_customer_identity_verified(user))
        status = build_verification_status(user)
        self.assertTrue(status['phone_verified'])
        self.assertTrue(status['identity_verified'])
        self.assertFalse(status['email_verified'])

    def test_google_only_verified(self):
        user = User.objects.create_user(username='g_only', email='', password='x')
        user.set_unusable_password()
        user.save()
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        CustomerProfile.objects.create(user=user, is_email_verified=False, is_phone_verified=False)
        SocialIdentity.objects.create(
            user=user,
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id='g-only-1',
        )
        self.assertTrue(is_customer_identity_verified(user))
        status = build_verification_status(user)
        self.assertTrue(status['google_verified'])
        self.assertTrue(status['identity_verified'])
        self.assertFalse(status['email_verified'])
        self.assertFalse(status['phone_verified'])

    def test_facebook_only_verified(self):
        user = User.objects.create_user(username='fb_only', email='', password='x')
        user.set_unusable_password()
        user.save()
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        CustomerProfile.objects.create(user=user, is_email_verified=False, is_phone_verified=False)
        SocialIdentity.objects.create(
            user=user,
            provider=SocialIdentity.Provider.FACEBOOK,
            provider_user_id='fb-only-1',
        )
        self.assertTrue(is_customer_identity_verified(user))
        status = build_verification_status(user)
        self.assertTrue(status['facebook_verified'])
        self.assertTrue(status['identity_verified'])

    def test_fully_unverified(self):
        user = User.objects.create_user(
            username='none',
            email='none@example.com',
            password='StrongPassword123',
        )
        user.groups.add(Group.objects.get(name='CUSTOMER'))
        CustomerProfile.objects.create(
            user=user,
            is_email_verified=False,
            is_phone_verified=False,
        )
        self.assertFalse(is_customer_identity_verified(user))
        status = build_verification_status(user)
        self.assertFalse(status['identity_verified'])
