"""Cancel reason_code persistence and API validation."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import CustomerSubscription, SubscriptionCancellation
from orders.services.subscription_service import cancel_subscription, subscribe_customer
from user_management.models import AdminProfile, CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (40, 40), 'blue').save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media')
class SubscriptionCancellationReasonTests(APITestCase):
    def setUp(self):
        self.today = date(2026, 8, 10)
        self._today = patch(
            'orders.services.subscription_service.business_today',
            return_value=self.today,
        )
        self._today.start()
        self.addCleanup(self._today.stop)
        self._publish = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish.start()
        self.addCleanup(self._publish.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.meal = MealCategory.objects.create(
            meal_name='Cancel Reason Plan',
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('cancel-reason.jpg'),
            is_active=True,
            is_subscribable=True,
        )

        self.customer_user = User.objects.create_user(
            username='cancel_reason_customer',
            email='cancel_reason_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712999001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)
        credit_wallet(get_or_create_wallet(self.customer), Decimal('5000.00'))

        self.admin_user = User.objects.create_user(
            username='cancel_reason_admin',
            email='cancel_reason_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.cancel_url = reverse('subscriptions:subscription-cancel-current')
        self.admin_cancel_url = reverse(
            'web_customers:admin-customer-cancel-subscription',
            kwargs={'public_id': self.customer.public_id},
        )

    def _subscribe(self):
        return subscribe_customer(
            self.customer,
            self.meal,
            meal_preference='both',
            today=self.today,
        )

    def test_customer_cancel_requires_reason_code(self):
        self._subscribe()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        response = self.client.post(self.cancel_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn('reason_code', response.data)
        sub = CustomerSubscription.objects.get(customer=self.customer)
        self.assertEqual(sub.status, CustomerSubscription.Status.ACTIVE)
        self.assertEqual(SubscriptionCancellation.objects.count(), 0)

    def test_customer_cancel_rejects_unknown_reason(self):
        self._subscribe()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        response = self.client.post(
            self.cancel_url,
            {'reason_code': 'unknown'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        sub = CustomerSubscription.objects.get(customer=self.customer)
        self.assertEqual(sub.status, CustomerSubscription.Status.ACTIVE)

    def test_customer_cancel_persists_reason(self):
        self._subscribe()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        response = self.client.post(
            self.cancel_url,
            {'reason_code': 'price_too_high', 'reason_text': 'too expensive'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = SubscriptionCancellation.objects.get(customer=self.customer)
        self.assertEqual(row.reason_code, 'price_too_high')
        self.assertEqual(row.reason_text, 'too expensive')
        self.assertEqual(row.cancelled_by, SubscriptionCancellation.CancelledBy.CUSTOMER)

    @patch(
        'orders.services.subscription_service.estimate_delivery_charge',
        return_value=Decimal('100.00'),
    )
    def test_admin_cancel_persists_reason(self, _mock_estimate):
        self._subscribe()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        response = self.client.post(
            self.admin_cancel_url,
            {'reason_code': 'food_taste', 'reason_text': 'ops note'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = SubscriptionCancellation.objects.get(customer=self.customer)
        self.assertEqual(row.reason_code, 'food_taste')
        self.assertEqual(row.cancelled_by, SubscriptionCancellation.CancelledBy.ADMIN)

    def test_system_cancel_path(self):
        sub = self._subscribe()
        cancel_subscription(
            sub,
            cancel_source=CustomerSubscription.CancelSource.SYSTEM,
            reason_code='temporary_pause',
        )
        row = SubscriptionCancellation.objects.get(subscription=sub)
        self.assertEqual(row.cancelled_by, SubscriptionCancellation.CancelledBy.SYSTEM)
        self.assertEqual(row.reason_code, 'temporary_pause')

    def test_service_rejects_unknown_reason_code(self):
        sub = self._subscribe()
        with self.assertRaises(ValueError):
            cancel_subscription(
                sub,
                cancel_source=CustomerSubscription.CancelSource.CUSTOMER,
                reason_code='unknown',
            )
        sub.refresh_from_db()
        self.assertEqual(sub.status, CustomerSubscription.Status.ACTIVE)
