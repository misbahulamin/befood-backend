"""Tests for lifetime Test Meal ordering (non-subscribers, manual payment)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import (
    OrderDelivery,
    OrderWalletSettings,
    TestMealFunnelEvent,
    TestMealOrder,
    TestMealPaymentEvent,
)
from orders.services.meal_demand import get_demand
from orders.services.order_delivery import mark_delivery
from orders.services.subscription_service import subscribe_customer
from orders.services import test_meal as test_meal_service
from orders.services.test_meal import (
    QUOTA_EXHAUSTED_BN,
    TestMealValidationError,
    _resolve_owned_address,
    create_test_meal_order,
    eligibility_for_customer,
    transition_test_meal_order_status,
)
from service_area.services.verification import (
    SERVICE_AREA_UNAVAILABLE,
    ServiceAreaError,
)
from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot
from user_management.models import AdminProfile, CustomerDeliveryPlace, CustomerProfile
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(
    MEDIA_ROOT='test_media',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SERVICE_AREA_ORDER_GATE_ENABLED=False,
)
class TestMealOrderTests(APITestCase):
    def setUp(self):
        self.today = date(2026, 11, 16)
        self.tz = ZoneInfo('Asia/Dhaka')
        self.now = datetime(2026, 11, 16, 10, 0, 0, tzinfo=self.tz)

        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=self.today,
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._tm_today_patcher = patch(
            'orders.services.test_meal.business_today',
            return_value=self.today,
        )
        self._tm_today_patcher.start()
        self.addCleanup(self._tm_today_patcher.stop)
        self._cutoff_patcher = patch(
            'orders.services.test_meal.is_past_meal_cutoff',
            return_value=False,
        )
        self._cutoff_patcher.start()
        self.addCleanup(self._cutoff_patcher.stop)
        self._serviceable_patcher = patch(
            'orders.services.test_meal.assert_serviceable',
            return_value=None,
        )
        self._serviceable_patcher.start()
        self.addCleanup(self._serviceable_patcher.stop)
        self._now_patcher = patch(
            'django.utils.timezone.now',
            return_value=self.now,
        )
        self._now_patcher.start()
        self.addCleanup(self._now_patcher.stop)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.customer_user = User.objects.create_user(
            username='test_meal_customer',
            email='test_meal@example.com',
            password='StrongPassword123',
            is_active=True,
            first_name='Test',
            last_name='Customer',
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712888001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.customer_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.other_user = User.objects.create_user(
            username='test_meal_other',
            email='test_meal_other@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.other_user.groups.add(customer_group)
        self.other = CustomerProfile.objects.create(
            user=self.other_user,
            phone='1712888002',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)
        self.other_place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.other,
            label='Other Home',
            full_address='Other address',
            area='Agrabad',
            city='Chittagong',
            latitude=Decimal('22.330000'),
            longitude=Decimal('91.830000'),
        )

        self.admin_user = User.objects.create_user(
            username='test_meal_admin',
            email='test_meal_admin@example.com',
            password='StrongPassword123',
            is_active=True,
            is_staff=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.plan = MealCategory.objects.create(
            meal_name='Test Meal Plan',
            description='Plan',
            meal_thumbnail=make_test_image(),
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('1800.00'),
            is_active=True,
            is_subscribable=True,
        )
        self.inactive_plan = MealCategory.objects.create(
            meal_name='Inactive Plan',
            description='Inactive',
            meal_thumbnail=make_test_image(name='inactive.jpg'),
            meal_period=MealCategory.MealPeriod.BOTH,
            total_price=Decimal('1800.00'),
            is_active=False,
            is_subscribable=True,
        )
        ensure_priced_delivery_slot(
            self.plan, self.today, 'lunch', price=Decimal('59.84')
        )
        ensure_priced_delivery_slot(
            self.plan, self.today, 'dinner', price=Decimal('70.00')
        )
        ensure_priced_delivery_slot(
            self.plan, self.today + timedelta(days=1), 'lunch', price=Decimal('59.84')
        )

        settings_obj = OrderWalletSettings.load()
        settings_obj.min_wallet_balance_to_order = Decimal('100.00')
        settings_obj.low_balance_reminder_threshold = Decimal('50.00')
        settings_obj.meal_stop_threshold = Decimal('20.00')
        settings_obj.test_meal_box_price = Decimal('10.00')
        settings_obj.test_meal_lifetime_quota = 2
        settings_obj.save()

        self.place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.customer,
            label='Home',
            full_address='House 1, Road 2',
            area='Agrabad',
            city='Chittagong',
            latitude=Decimal('22.330000'),
            longitude=Decimal('91.830000'),
        )

        wallet = get_or_create_wallet(self.customer)
        credit_wallet(wallet, Decimal('500.00'), note='seed')
        wallet.refresh_from_db()
        self.wallet_balance_before = wallet.recharge_balance

    def _create_payload(self, **overrides):
        payload = {
            'service_date': self.today.isoformat(),
            'meal_period': 'lunch',
            'package_public_id': str(self.plan.public_id),
            'address_public_id': str(self.place.public_id),
            'special_instructions': '',
        }
        payload.update(overrides)
        return payload

    def _create_via_service(self, *, key=None, service_date=None, meal_period='lunch'):
        return create_test_meal_order(
            self.customer,
            service_date=service_date or self.today,
            meal_period=meal_period,
            package_public_id=self.plan.public_id,
            address_public_id=self.place.public_id,
            idempotency_key=key,
        )

    def test_settings_get_patch_round_trip(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        get_resp = self.client.get('/api/v1/web/orders/order-wallet-settings/')
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data['test_meal_box_price'], '10.00')
        self.assertEqual(get_resp.data['test_meal_lifetime_quota'], 2)

        patch_resp = self.client.patch(
            '/api/v1/web/orders/order-wallet-settings/',
            {'test_meal_box_price': '12.50', 'test_meal_lifetime_quota': 3},
            format='json',
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_resp.data['test_meal_box_price'], '12.50')
        self.assertEqual(patch_resp.data['test_meal_lifetime_quota'], 3)
        settings_obj = OrderWalletSettings.load()
        self.assertEqual(settings_obj.test_meal_box_price, Decimal('12.50'))
        self.assertEqual(settings_obj.test_meal_lifetime_quota, 3)

    def test_eligibility_eligible_and_unauthenticated(self):
        resp = self.client.get('/api/v1/test-meals/eligibility/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['eligible'])
        self.assertEqual(resp.data['quota_limit'], 2)
        self.assertEqual(resp.data['quota_used'], 0)
        self.assertEqual(resp.data['quota_remaining'], 2)
        self.assertIsNone(resp.data['reason'])

        self.client.credentials()
        unauth = self.client.get('/api/v1/test-meals/eligibility/')
        self.assertEqual(unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_eligibility_active_subscriber_and_quota_exhausted(self):
        with patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        ), patch(
            'orders.services.subscription_service.is_past_meal_cutoff',
            return_value=False,
        ):
            subscribe_customer(self.customer, self.plan, today=self.today)
        resp = self.client.get('/api/v1/test-meals/eligibility/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['eligible'])
        self.assertEqual(resp.data['reason'], 'ACTIVE_SUBSCRIBER')

        # Switch to another non-subscriber with exhausted quota.
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        for i in range(2):
            create_test_meal_order(
                self.other,
                service_date=self.today,
                meal_period='lunch',
                package_public_id=self.plan.public_id,
                address_public_id=self.other_place.public_id,
                idempotency_key=f'quota-{i}',
            )
        exhausted = eligibility_for_customer(self.other)
        self.assertFalse(exhausted['eligible'])
        self.assertEqual(exhausted['reason'], 'QUOTA_EXHAUSTED')
        self.assertEqual(exhausted['message_bn'], QUOTA_EXHAUSTED_BN)

    def test_packages_exclude_inactive(self):
        resp = self.client.get('/api/v1/test-meals/packages/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {row['name'] for row in resp.data}
        self.assertIn('Test Meal Plan', names)
        self.assertNotIn('Inactive Plan', names)

    def test_quote_pricing_and_past_date_and_no_persist(self):
        resp = self.client.post(
            '/api/v1/test-meals/quote/',
            {
                'service_date': self.today.isoformat(),
                'meal_period': 'lunch',
                'package_public_id': str(self.plan.public_id),
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['meal_price'], '59.84')
        self.assertEqual(resp.data['box_charge'], '10.00')
        self.assertEqual(resp.data['total_price'], '69.84')
        self.assertEqual(resp.data['delivery_window_start'], '11:00')
        self.assertEqual(resp.data['delivery_window_end'], '14:00')
        self.assertEqual(TestMealOrder.objects.count(), 0)

        past = self.client.post(
            '/api/v1/test-meals/quote/',
            {
                'service_date': (self.today - timedelta(days=1)).isoformat(),
                'meal_period': 'lunch',
                'package_public_id': str(self.plan.public_id),
            },
            format='json',
        )
        self.assertEqual(past.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(past.data['error_code'], 'INVALID_DATE')

    def test_create_success_no_wallet_debit_and_delivery_stop(self):
        resp = self.client.post(
            '/api/v1/test-meals/orders/',
            self._create_payload(),
            format='json',
            HTTP_IDEMPOTENCY_KEY='create-1',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['order_status'], 'confirmed')
        self.assertEqual(resp.data['payment_status'], 'unpaid')
        self.assertEqual(resp.data['payment_method'], 'manual')
        self.assertEqual(resp.data['total_price'], '69.84')

        order = TestMealOrder.objects.get(public_id=resp.data['public_id'])
        delivery = OrderDelivery.objects.get(test_meal_order=order)
        self.assertIsNone(delivery.order_id)
        self.assertIsNone(delivery.subscription_id)
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)

        wallet = get_or_create_wallet(self.customer)
        wallet.refresh_from_db()
        self.assertEqual(wallet.recharge_balance, self.wallet_balance_before)

    def test_idempotent_replay_and_conflict(self):
        first = self.client.post(
            '/api/v1/test-meals/orders/',
            self._create_payload(),
            format='json',
            HTTP_IDEMPOTENCY_KEY='same-key',
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        replay = self.client.post(
            '/api/v1/test-meals/orders/',
            self._create_payload(),
            format='json',
            HTTP_IDEMPOTENCY_KEY='same-key',
        )
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data.get('idempotent_replay'))
        self.assertEqual(replay.data['public_id'], first.data['public_id'])
        self.assertEqual(TestMealOrder.objects.filter(customer=self.customer).count(), 1)

        conflict = self.client.post(
            '/api/v1/test-meals/orders/',
            self._create_payload(meal_period='dinner'),
            format='json',
            HTTP_IDEMPOTENCY_KEY='same-key',
        )
        self.assertEqual(conflict.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(conflict.data['error_code'], 'IDEMPOTENCY_CONFLICT')

    def test_quota_third_order_rejected(self):
        self._create_via_service(key='q1')
        self._create_via_service(key='q2', meal_period='dinner')
        resp = self.client.post(
            '/api/v1/test-meals/orders/',
            self._create_payload(service_date=(self.today + timedelta(days=1)).isoformat()),
            format='json',
            HTTP_IDEMPOTENCY_KEY='q3',
        )
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(resp.data['error_code'], 'QUOTA_EXHAUSTED')
        self.assertEqual(TestMealOrder.objects.filter(customer=self.customer).count(), 2)

    def test_other_customer_address_and_order_denied(self):
        bad_addr = self.client.post(
            '/api/v1/test-meals/orders/',
            self._create_payload(address_public_id=str(self.other_place.public_id)),
            format='json',
        )
        self.assertEqual(bad_addr.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(bad_addr.data['error_code'], 'ADDRESS_NOT_FOUND')

        order, _ = self._create_via_service(key='owner-order')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        detail = self.client.get(f'/api/v1/test-meals/orders/{order.public_id}/')
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_null_coordinate_place_accepted_out_of_zone_still_rejected(self):
        """Subscription-style null coords skip assert; present coords still gated."""
        null_place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.customer,
            label='Manual Home',
            full_address='House without GPS',
            area='Agrabad',
            city='Chittagong',
            latitude=None,
            longitude=None,
        )
        with patch.object(test_meal_service, 'assert_serviceable') as mock_assert:
            resolved = _resolve_owned_address(self.customer, null_place.public_id)
            self.assertEqual(resolved.public_id, null_place.public_id)
            mock_assert.assert_not_called()

        with patch.object(
            test_meal_service,
            'assert_serviceable',
            side_effect=ServiceAreaError(
                'BeFood service is not available at this delivery location.',
                code=SERVICE_AREA_UNAVAILABLE,
            ),
        ) as mock_assert:
            with self.assertRaises(TestMealValidationError) as ctx:
                _resolve_owned_address(self.customer, self.place.public_id)
            self.assertEqual(ctx.exception.code, SERVICE_AREA_UNAVAILABLE)
            mock_assert.assert_called_once()

    def test_admin_record_payment_idempotent_and_customer_denied(self):
        order, _ = self._create_via_service(key='pay-1')
        denied = self.client.get('/api/v1/web/orders/test-meals/orders/')
        self.assertIn(denied.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        pay = self.client.post(
            f'/api/v1/web/orders/test-meals/orders/{order.public_id}/record-payment/',
            {'notes': 'cash'},
            format='json',
        )
        self.assertEqual(pay.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, TestMealOrder.PaymentStatus.PAID)
        self.assertEqual(order.order_status, TestMealOrder.OrderStatus.CONFIRMED)
        self.assertEqual(order.amount_collected, Decimal('69.84'))
        self.assertEqual(TestMealPaymentEvent.objects.filter(order=order).count(), 1)

        again = self.client.post(
            f'/api/v1/web/orders/test-meals/orders/{order.public_id}/record-payment/',
            {'notes': 'retry'},
            format='json',
        )
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.amount_collected, Decimal('69.84'))
        self.assertEqual(TestMealPaymentEvent.objects.filter(order=order).count(), 1)

        filtered = self.client.get(
            '/api/v1/web/orders/test-meals/orders/',
            {'meal_period': 'lunch', 'payment_status': 'paid'},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(filtered.data['results']), 1)

    def test_funnel_event_dedupe_does_not_create_order(self):
        body = {
            'event_name': 'cta_click',
            'client_event_id': 'evt-1',
            'correlation_id': 'corr-1',
        }
        first = self.client.post('/api/v1/test-meals/funnel-events/', body, format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post('/api/v1/test-meals/funnel-events/', body, format='json')
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(
            TestMealFunnelEvent.objects.filter(client_event_id='evt-1').count(),
            1,
        )
        self.assertEqual(TestMealOrder.objects.count(), 0)

    def test_demand_includes_test_meal_excludes_cancelled(self):
        order, _ = self._create_via_service(key='demand-1')
        demand = get_demand(self.today, 'lunch')
        self.assertEqual(demand.test_meal_count, 1)
        self.assertGreaterEqual(demand.final_cooking_count, 1)

        transition_test_meal_order_status(
            order,
            to_status=TestMealOrder.OrderStatus.CANCELLED,
            reason='customer cancel',
        )
        demand2 = get_demand(self.today, 'lunch')
        self.assertEqual(demand2.test_meal_count, 0)

    def test_mark_delivered_syncs_without_wallet_charge(self):
        order, _ = self._create_via_service(key='deliver-1')
        delivery = OrderDelivery.objects.get(test_meal_order=order)
        marked = mark_delivery(
            delivery,
            to_status=OrderDelivery.DeliveryStatus.DELIVERED,
            marked_by=self.admin_user,
        )
        self.assertEqual(marked.status, OrderDelivery.DeliveryStatus.DELIVERED)
        order.refresh_from_db()
        self.assertEqual(order.order_status, TestMealOrder.OrderStatus.DELIVERED)
        self.assertEqual(order.payment_status, TestMealOrder.PaymentStatus.UNPAID)
        wallet = get_or_create_wallet(self.customer)
        wallet.refresh_from_db()
        self.assertEqual(wallet.recharge_balance, self.wallet_balance_before)

    def test_analytics_revenue_and_empty_conversion_safe(self):
        order, _ = self._create_via_service(key='analytics-1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        emptyish = self.client.get('/api/v1/web/orders/test-meals/analytics/')
        self.assertEqual(emptyish.status_code, status.HTTP_200_OK)
        self.assertEqual(emptyish.data['confirmed_order_value'], '69.84')
        self.assertEqual(emptyish.data['collected_revenue'], '0.00')
        self.assertEqual(emptyish.data['outstanding_amount'], '69.84')
        self.assertEqual(emptyish.data['primary_conversion_rate'], 0.0)

        self.client.post(
            f'/api/v1/web/orders/test-meals/orders/{order.public_id}/record-payment/',
            {},
            format='json',
        )
        paid = self.client.get('/api/v1/web/orders/test-meals/analytics/')
        self.assertEqual(paid.data['collected_revenue'], '69.84')
        self.assertEqual(paid.data['outstanding_amount'], '0.00')

    def test_price_change_after_confirm_preserves_snapshot(self):
        order, _ = self._create_via_service(key='snap-1')
        ensure_priced_delivery_slot(
            self.plan, self.today, 'lunch', price=Decimal('80.00')
        )
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('69.84'))
