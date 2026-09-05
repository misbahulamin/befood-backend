from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import CustomerSubscription, Order, OrderDelivery, OrderWalletSettings
from orders.services.meal_demand import get_demand
from orders.services.meal_off import customer_meal_off
from orders.services.order_delivery import mark_delivery
from orders.services.order_service import create_meal_order
from orders.services.subscription_migration import migrate_in_flight_orders
from orders.services.order_service import FrozenWalletOrderError, InsufficientWalletBalanceError
from orders.services.subscription_service import (
    AlreadySubscribedError,
    PlanUnavailableError,
    ensure_subscription_deliveries,
    subscribe_customer,
)
from user_management.models import AdminProfile, CustomerProfile
from wallet.models import Wallet, WalletTransaction
from wallet.services.ledger import credit_wallet, get_or_create_wallet


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _set_wallet_min(amount: Decimal) -> None:
    settings_obj = OrderWalletSettings.load()
    settings_obj.min_wallet_balance_to_order = amount
    settings_obj.save()


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CustomerSubscriptionAPITestCase(APITestCase):
    def setUp(self):
        self._today_patcher = patch(
            'orders.services.subscription_service.business_today',
            return_value=date(2026, 7, 10),
        )
        self._today_patcher.start()
        self.addCleanup(self._today_patcher.stop)
        self._publish_patcher = patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._publish_patcher.start()
        self.addCleanup(self._publish_patcher.stop)
        self._order_publish_patcher = patch(
            'orders.services.order_service.published_schedule_for_meal',
            return_value=object(),
        )
        self._order_publish_patcher.start()
        self.addCleanup(self._order_publish_patcher.stop)

        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')

        self.customer_user = User.objects.create_user(
            username='sub_customer',
            email='sub_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712555001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.other_user = User.objects.create_user(
            username='sub_other',
            email='sub_other@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.other_user.groups.add(self.customer_group)
        self.other_profile = CustomerProfile.objects.create(
            user=self.other_user,
            phone='1712555002',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.unverified_user = User.objects.create_user(
            username='sub_unverified',
            email='sub_unverified@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.unverified_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=self.unverified_user,
            phone='1712555003',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=False,
        )
        self.unverified_token = Token.objects.create(user=self.unverified_user)

        self.admin_user = User.objects.create_user(
            username='sub_admin',
            email='sub_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(self.admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.plan = MealCategory.objects.create(
            meal_name='Regular Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('regular-sub.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        self.inactive_plan = MealCategory.objects.create(
            meal_name='Inactive Plan',
            total_price=Decimal('1000.00'),
            meal_thumbnail=make_test_image('inactive-sub.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=False,
            is_subscribable=True,
        )
        self.non_subscribable = MealCategory.objects.create(
            meal_name='Daily Box',
            total_price=Decimal('180.00'),
            meal_thumbnail=make_test_image('daily-sub.jpg'),
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
            is_subscribable=False,
        )
        _set_wallet_min(Decimal('0.00'))

        self.plans_url = reverse('subscription_plans:subscription-plan-list')
        self.subscriptions_url = reverse('subscriptions:subscription-list')
        self.current_url = reverse('subscriptions:subscription-current')
        self.cancel_url = reverse('subscriptions:subscription-cancel-current')
        self.admin_subs_url = reverse('web_subscriptions:admin-subscription-list')
        self.admin_plans_url = reverse('web_subscription_plans:admin-subscription-plan-list')
        self.order_create_url = reverse('orders:order-list')
        self.current_package_url = reverse('orders:order-current-package')

    def _auth(self, token=None):
        token = token or self.customer_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def _subscribe_payload(self, plan=None):
        plan = plan or self.plan
        return {'plan_public_id': str(plan.public_id)}

    def test_catalog_lists_active_subscribable_plans_only(self):
        self._auth()
        response = self.client.get(self.plans_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row['meal_name'] for row in response.data}
        self.assertIn('Regular Package', names)
        self.assertNotIn('Inactive Plan', names)
        self.assertNotIn('Daily Box', names)
        self.assertTrue(all(row['is_subscribable'] for row in response.data))

    def test_subscribe_success_no_order_no_wallet_debit(self):
        wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(wallet, Decimal('200.00'))
        self._auth()
        response = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['status'], 'active')
        self.assertEqual(response.data['meal_name_snapshot'], 'Regular Package')
        self.assertEqual(response.data['meal_period_snapshot'], 'both')
        self.assertEqual(response.data['started_on'], '2026-07-10')
        self.assertEqual(Order.objects.filter(customer=self.customer_profile).count(), 0)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('200.00'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=wallet, type=WalletTransaction.Type.PAYMENT
            ).count(),
            0,
        )
        self.assertTrue(
            CustomerSubscription.objects.filter(
                customer=self.customer_profile,
                status=CustomerSubscription.Status.ACTIVE,
            ).exists()
        )

    def test_subscribe_rejects_inactive_and_non_subscribable_plan(self):
        self._auth()
        inactive = self.client.post(
            self.subscriptions_url, self._subscribe_payload(self.inactive_plan), format='json'
        )
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            self.subscriptions_url, {'plan_public_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}, format='json'
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        daily = self.client.post(
            self.subscriptions_url, self._subscribe_payload(self.non_subscribable), format='json'
        )
        self.assertEqual(daily.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CustomerSubscription.objects.count(), 0)

    def test_unauthenticated_and_unverified_cannot_subscribe(self):
        bare = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(bare.status_code, status.HTTP_401_UNAUTHORIZED)
        self._auth(self.unverified_token)
        unverified = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(unverified.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Identity verification', str(unverified.data))
        self.assertNotIn('Email verification is required', str(unverified.data))

    def test_phone_verified_customer_can_subscribe(self):
        phone_user = User.objects.create_user(
            username='sub_phone',
            email='',
            password='StrongPassword123',
            is_active=True,
        )
        phone_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=phone_user,
            phone='1712555099',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=False,
            is_phone_verified=True,
        )
        token = Token.objects.create(user=phone_user)
        self._auth(token)
        response = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_facebook_linked_customer_can_subscribe(self):
        from user_management.models import SocialIdentity

        fb_user = User.objects.create_user(
            username='sub_fb',
            email='',
            password='StrongPassword123',
            is_active=True,
        )
        fb_user.set_unusable_password()
        fb_user.save()
        fb_user.groups.add(self.customer_group)
        CustomerProfile.objects.create(
            user=fb_user,
            phone='1712555098',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=False,
            is_phone_verified=False,
        )
        SocialIdentity.objects.create(
            user=fb_user,
            provider=SocialIdentity.Provider.FACEBOOK,
            provider_user_id='fb-sub-1',
        )
        token = Token.objects.create(user=fb_user)
        self._auth(token)
        response = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_second_active_subscribe_rejected_then_allowed_after_cancel(self):
        self._auth()
        first = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already have an active meal subscription', str(second.data).lower())
        cancel = self.client.post(self.cancel_url, {}, format='json')
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data['status'], 'cancelled')
        third = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(third.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            CustomerSubscription.objects.filter(
                customer=self.customer_profile,
                status=CustomerSubscription.Status.ACTIVE,
            ).count(),
            1,
        )

    def test_frozen_wallet_and_below_minimum_and_missing_wallet(self):
        _set_wallet_min(Decimal('500.00'))
        self._auth()
        missing = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient wallet balance', str(missing.data))

        wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(wallet, Decimal('100.00'))
        low = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(low.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subscribe', str(low.data).lower())

        wallet.status = Wallet.Status.FROZEN
        wallet.save(update_fields=['status'])
        frozen = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        self.assertEqual(frozen.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('frozen', str(frozen.data).lower())
        self.assertEqual(CustomerSubscription.objects.count(), 0)

    def test_already_subscribed_error_before_wallet_error(self):
        subscribe_customer(self.customer_profile, self.plan, today=date(2026, 7, 10))
        _set_wallet_min(Decimal('500.00'))
        self.assertFalse(Wallet.objects.filter(customer=self.customer_profile).exists())
        with self.assertRaises(AlreadySubscribedError):
            subscribe_customer(self.customer_profile, self.plan, today=date(2026, 7, 10))

    def test_service_rejects_unavailable_plan_and_wallet_gates(self):
        with self.assertRaises(PlanUnavailableError):
            subscribe_customer(self.customer_profile, self.inactive_plan)
        _set_wallet_min(Decimal('500.00'))
        with self.assertRaises(InsufficientWalletBalanceError):
            subscribe_customer(self.customer_profile, self.plan)
        wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(wallet, Decimal('1000.00'))
        wallet.status = Wallet.Status.FROZEN
        wallet.save(update_fields=['status'])
        with self.assertRaises(FrozenWalletOrderError):
            subscribe_customer(self.customer_profile, self.plan)

    def test_current_and_isolation_and_current_package(self):
        self._auth()
        empty = self.client.get(self.current_url)
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertIsNone(empty.data['current_subscription'])
        created = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        public_id = created.data['public_id']
        current = self.client.get(self.current_url)
        self.assertEqual(current.data['current_subscription']['public_id'], public_id)
        detail = self.client.get(
            reverse('subscriptions:subscription-detail', kwargs={'public_id': public_id})
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self._auth(self.other_token)
        hidden = self.client.get(
            reverse('subscriptions:subscription-detail', kwargs={'public_id': public_id})
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self._auth()
        package = self.client.get(self.current_package_url)
        self.assertEqual(package.status_code, status.HTTP_200_OK)
        self.assertEqual(package.data['current_package']['public_id'], public_id)
        self.assertEqual(package.data['current_subscription']['public_id'], public_id)

    def test_cancel_skips_future_not_today_and_foreign_cancel_hidden(self):
        self._auth()
        created = self.client.post(self.subscriptions_url, self._subscribe_payload(), format='json')
        public_id = created.data['public_id']
        subscription = CustomerSubscription.objects.get(public_id=public_id)
        today_slots = list(
            subscription.deliveries.filter(service_date=date(2026, 7, 10), status='scheduled')
        )
        future_count = subscription.deliveries.filter(
            service_date__gt=date(2026, 7, 10), status='scheduled'
        ).count()
        self.assertGreater(len(today_slots), 0)
        self.assertGreater(future_count, 0)
        self._auth(self.other_token)
        denied = self.client.post(self.cancel_url, {}, format='json')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, CustomerSubscription.Status.ACTIVE)
        self._auth()
        cancel = self.client.post(self.cancel_url, {}, format='json')
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, CustomerSubscription.Status.CANCELLED)
        self.assertEqual(subscription.cancel_effective_on, date(2026, 7, 10))
        for slot in today_slots:
            slot.refresh_from_db()
            self.assertEqual(slot.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertEqual(
            subscription.deliveries.filter(
                service_date__gt=date(2026, 7, 10),
                status=OrderDelivery.DeliveryStatus.SKIPPED,
                skip_source=OrderDelivery.SkipSource.SYSTEM,
            ).count(),
            future_count,
        )

    def test_legacy_order_create_and_orderable_months_rejected(self):
        self._auth()
        create = self.client.post(
            self.order_create_url,
            {'meal_public_id': str(self.plan.public_id)},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(create.data['error_code'], 'SUBSCRIBE_REQUIRED')
        self.assertEqual(Order.objects.count(), 0)
        months = self.client.get(
            reverse('orders:order-orderable-months'),
            {'meal_public_id': str(self.plan.public_id)},
        )
        self.assertEqual(months.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(months.data['error_code'], 'SUBSCRIBE_REQUIRED')

    def test_admin_list_filters_and_permissions(self):
        subscribe_customer(self.customer_profile, self.plan, today=date(2026, 7, 10))
        response = self.client.get(self.admin_subs_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self._auth()
        forbidden = self.client.get(self.admin_subs_url)
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self._auth(self.admin_token)
        listed = self.client.get(self.admin_subs_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(listed.data['count'], 1)
        active = self.client.get(self.admin_subs_url, {'status': 'active'})
        self.assertTrue(all(row['status'] == 'active' for row in active.data['results']))
        by_plan = self.client.get(
            self.admin_subs_url, {'plan_public_id': str(self.plan.public_id)}
        )
        self.assertGreaterEqual(by_plan.data['count'], 1)
        bad_status = self.client.get(self.admin_subs_url, {'status': 'paused'})
        self.assertEqual(bad_status.status_code, status.HTTP_400_BAD_REQUEST)
        unknown = self.client.get(self.admin_subs_url, {'foo': '1'})
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_plan_crud(self):
        self._auth(self.admin_token)
        created = self.client.post(
            self.admin_plans_url,
            {
                'meal_name': 'Premium Plan',
                'meal_period': 'both',
                'description': 'Ongoing premium',
                'is_active': True,
                'is_subscribable': True,
                'meal_thumbnail': make_test_image('premium-plan.jpg'),
            },
            format='multipart',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertTrue(created.data['is_subscribable'])
        public_id = created.data['public_id']
        patched = self.client.patch(
            reverse(
                'web_subscription_plans:admin-subscription-plan-detail',
                kwargs={'public_id': public_id},
            ),
            {'meal_name': 'Premium Plus'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['meal_name'], 'Premium Plus')

    def test_rolling_slots_idempotent_unpublished_month_and_month_end(self):
        def published(_meal_id, year, month):
            if (year, month) == (2026, 7):
                return object()
            return None

        with patch(
            'orders.services.subscription_service.published_schedule_for_meal',
            side_effect=published,
        ):
            subscription = subscribe_customer(
                self.customer_profile, self.plan, today=date(2026, 7, 10)
            )
            first = subscription.deliveries.count()
            self.assertGreater(first, 0)
            self.assertFalse(
                subscription.deliveries.filter(service_date__month=8).exists()
            )
            ensure_subscription_deliveries(subscription, today=date(2026, 7, 10))
            self.assertEqual(subscription.deliveries.count(), first)
            ensure_subscription_deliveries(subscription, today=date(2026, 7, 31))
            subscription.refresh_from_db()
            self.assertEqual(subscription.status, CustomerSubscription.Status.ACTIVE)
            self.assertFalse(
                subscription.deliveries.filter(service_date__month=8).exists()
            )

    def test_meal_off_does_not_cancel_subscription(self):
        subscription = subscribe_customer(
            self.customer_profile, self.plan, today=date(2026, 7, 10)
        )
        delivery = subscription.deliveries.get(
            service_date=date(2026, 7, 11), meal_period='lunch'
        )
        self.assertIsNone(delivery.order_id)
        self.assertEqual(delivery.subscription_id, subscription.pk)
        tz = ZoneInfo('Asia/Dhaka')
        now = datetime(2026, 7, 10, 10, 0, tzinfo=tz)
        with patch('orders.services.meal_off.meal_off_business_now', return_value=now):
            updated = customer_meal_off(delivery, user=self.customer_user, note='Travel')
        self.assertEqual(updated.status, OrderDelivery.DeliveryStatus.SKIPPED)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, CustomerSubscription.Status.ACTIVE)

    @patch('orders.services.meal_off.meal_off_business_now')
    def test_subscription_api_meal_off_and_meal_on(self, mock_now):
        """Postgres-safe lock: subscription-owned slots (order null) must not 500."""
        mock_now.return_value = datetime(2026, 7, 10, 10, 0, tzinfo=ZoneInfo('Asia/Dhaka'))
        subscription = subscribe_customer(
            self.customer_profile, self.plan, today=date(2026, 7, 10)
        )
        delivery = subscription.deliveries.get(
            service_date=date(2026, 7, 11), meal_period='lunch'
        )
        self.assertIsNone(delivery.order_id)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')
        off_url = reverse(
            'subscriptions:subscription-meal-off-noslash',
            kwargs={
                'public_id': subscription.public_id,
                'delivery_id': delivery.public_id,
            },
        )
        off_response = self.client.post(off_url, {'note': 'Travel'}, format='json')
        self.assertEqual(off_response.status_code, status.HTTP_200_OK, off_response.data)
        self.assertEqual(off_response.data['status'], 'skipped')
        self.assertEqual(off_response.data['skip_source'], 'customer')

        delivery.refresh_from_db()
        on_url = reverse(
            'subscriptions:subscription-meal-on-noslash',
            kwargs={
                'public_id': subscription.public_id,
                'delivery_id': delivery.public_id,
            },
        )
        on_response = self.client.post(on_url, {}, format='json')
        self.assertEqual(on_response.status_code, status.HTTP_200_OK, on_response.data)
        self.assertEqual(on_response.data['status'], 'scheduled')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        self.assertIsNone(delivery.skip_source)

    def test_demand_counts_subscription_slots(self):
        subscribe_customer(self.customer_profile, self.plan, today=date(2026, 7, 10))
        demand = get_demand(date(2026, 7, 10), 'lunch')
        self.assertGreaterEqual(demand.expected_meal_count, 1)
        by_name = {row.package_name: row for row in demand.packages}
        self.assertIn('Regular Package', by_name)

    def test_admin_api_mark_skip_on_subscription_slot(self):
        """Postgres-safe lock: admin skip on subscription-owned slot (order null) must not 500."""
        subscription = subscribe_customer(
            self.customer_profile, self.plan, today=date(2026, 7, 10)
        )
        delivery = subscription.deliveries.get(
            service_date=date(2026, 7, 11), meal_period='dinner'
        )
        self.assertIsNone(delivery.order_id)

        self._auth(self.admin_token)
        url = reverse(
            'web_subscriptions:admin-subscription-mark-delivery-noslash',
            kwargs={
                'public_id': subscription.public_id,
                'delivery_id': delivery.public_id,
            },
        )
        response = self.client.post(url, {'status': 'skipped', 'note': 'Admin skip'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'skipped')
        self.assertEqual(response.data['skip_source'], 'admin')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SKIPPED)
        self.assertEqual(delivery.skip_source, OrderDelivery.SkipSource.ADMIN)

    def test_admin_api_mark_delivered_on_subscription_slot(self):
        """Postgres-safe lock: admin deliver + wallet charge on subscription slot must not 500."""
        from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot

        wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(wallet, Decimal('500.00'))
        subscription = subscribe_customer(
            self.customer_profile, self.plan, today=date(2026, 7, 10)
        )
        delivery = subscription.deliveries.get(
            service_date=date(2026, 7, 10), meal_period='lunch'
        )
        self.assertIsNone(delivery.order_id)
        ensure_priced_delivery_slot(
            self.plan, delivery.service_date, delivery.meal_period, price=Decimal('62.00')
        )

        self._auth(self.admin_token)
        url = reverse(
            'web_subscriptions:admin-subscription-mark-delivery-noslash',
            kwargs={
                'public_id': subscription.public_id,
                'delivery_id': delivery.public_id,
            },
        )
        with patch(
            'orders.services.order_delivery.timezone.localdate',
            return_value=date(2026, 7, 10),
        ):
            response = self.client.post(url, {'status': 'delivered'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'delivered')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('438.00'))
        self.assertEqual(delivery.charged_amount, Decimal('62.00'))

    def test_delivered_debit_still_works_on_subscription_slot(self):
        from orders.tests.test_meal_delivery_wallet_payment import ensure_priced_delivery_slot

        wallet = get_or_create_wallet(self.customer_profile)
        credit_wallet(wallet, Decimal('500.00'))
        subscription = subscribe_customer(
            self.customer_profile, self.plan, today=date(2026, 7, 10)
        )
        delivery = subscription.deliveries.get(
            service_date=date(2026, 7, 10), meal_period='lunch'
        )
        ensure_priced_delivery_slot(
            self.plan, delivery.service_date, delivery.meal_period, price=Decimal('62.00')
        )
        with patch(
            'orders.services.order_delivery.timezone.localdate',
            return_value=date(2026, 7, 10),
        ):
            marked = mark_delivery(delivery, 'delivered', marked_by=self.admin_user)
        self.assertEqual(marked.status, OrderDelivery.DeliveryStatus.DELIVERED)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('438.00'))
        self.assertEqual(marked.charged_amount, Decimal('62.00'))

    def test_ensure_command_processes_active_subscriptions(self):
        subscribe_customer(self.customer_profile, self.plan, today=date(2026, 7, 10))
        call_command('ensure_subscription_deliveries', date='2026-07-10')

    @patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.order_service.timezone.localdate', return_value=date(2026, 7, 10))
    @patch('orders.services.meal_month.timezone.localdate', return_value=date(2026, 7, 10))
    def test_in_flight_order_migration_creates_one_subscription(self, *_mocks):
        july = create_meal_order(self.customer_profile, self.plan, year=2026, month=7)
        august = create_meal_order(self.customer_profile, self.plan, year=2026, month=8)
        before = july.deliveries.filter(service_date__gte=date(2026, 7, 10)).count()
        result = migrate_in_flight_orders(today=date(2026, 7, 10))
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['cancelled_extra'], 1)
        self.assertEqual(
            CustomerSubscription.objects.filter(customer=self.customer_profile).count(),
            1,
        )
        subscription = CustomerSubscription.objects.get(customer=self.customer_profile)
        self.assertEqual(subscription.status, CustomerSubscription.Status.ACTIVE)
        attached = july.deliveries.filter(
            service_date__gte=date(2026, 7, 10), subscription=subscription
        ).count()
        self.assertEqual(attached, before)
        self.assertEqual(subscription.deliveries.count(), before)
        august.refresh_from_db()
        self.assertEqual(august.order_status, Order.OrderStatus.CANCELLED)
        second = migrate_in_flight_orders(today=date(2026, 7, 10))
        self.assertEqual(second['created'], 0)
        self.assertEqual(
            CustomerSubscription.objects.filter(customer=self.customer_profile).count(),
            1,
        )

    def test_skips_customer_who_already_has_active_subscription(self):
        subscribe_customer(self.customer_profile, self.plan, today=date(2026, 7, 10))
        with patch('orders.services.order_duration.timezone.localdate', return_value=date(2026, 7, 10)):
            with patch(
                'orders.services.order_service.timezone.localdate',
                return_value=date(2026, 7, 10),
            ):
                with patch(
                    'orders.services.meal_month.timezone.localdate',
                    return_value=date(2026, 7, 10),
                ):
                    create_meal_order(self.customer_profile, self.plan, year=2026, month=7)
                    create_meal_order(self.other_profile, self.plan, year=2026, month=7)
        result = migrate_in_flight_orders(today=date(2026, 7, 10))
        self.assertEqual(
            CustomerSubscription.objects.filter(
                customer=self.customer_profile,
                status=CustomerSubscription.Status.ACTIVE,
            ).count(),
            1,
        )
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['skipped_existing'], 1)
