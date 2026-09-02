from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from meals.models import MealCategory
from orders.models import CustomerSubscription, Order, OrderDelivery
from user_management.models import AdminProfile, CustomerAddress, CustomerProfile
from wallet.models import Wallet, WalletTransaction


def make_test_image(name='meal.jpg', size=(40, 40), color='blue'):
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT='test_media', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminCustomerManagementAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin = User.objects.create_user(
            username='admin-cust',
            email='admin-cust@example.com',
            password='StrongPassword123',
            first_name='Admin',
            last_name='User',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin, is_verified=True)
        self.admin.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin)

        self.meal = MealCategory.objects.create(
            meal_name='Regular Package',
            total_price=Decimal('3000.00'),
            meal_thumbnail=make_test_image('admin-cust-meal.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )

        self.customer_a = self._make_customer(
            'alice',
            email='alice@example.com',
            phone='1711111111',
            first_name='Alice',
            last_name='Active',
            is_email_verified=True,
            is_active=True,
        )
        self.customer_b = self._make_customer(
            'bob',
            email='bob@example.com',
            phone='1722222222',
            first_name='Bob',
            last_name='Inactive',
            is_email_verified=False,
            is_active=False,
        )
        self.customer_c = self._make_customer(
            'carol',
            email='carol@example.com',
            phone='1733333333',
            first_name='Carol',
            last_name='NoOrder',
            is_email_verified=True,
            is_active=True,
        )
        self.customer_d = self._make_customer(
            'dave',
            email='dave@example.com',
            phone='1744444444',
            first_name='Dave',
            last_name='Subscriber',
            is_email_verified=True,
            is_active=True,
        )

        CustomerAddress.objects.create(
            customer_profile=self.customer_a,
            address_type=CustomerAddress.AddressType.PRESENT,
            full_address='12 Test Street',
            city='Dhaka',
            area='Banani',
            is_default_delivery=True,
        )

        self.order_a = self._create_active_order(self.customer_a)
        self.delivery_scheduled = OrderDelivery.objects.create(
            order=self.order_a,
            service_date=date(2026, 8, 6),
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        self.delivery_skipped = OrderDelivery.objects.create(
            order=self.order_a,
            service_date=date(2026, 8, 7),
            meal_period=OrderDelivery.MealPeriod.DINNER,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.CUSTOMER,
            note='Traveling',
        )
        OrderDelivery.objects.create(
            order=self.order_a,
            service_date=date(2026, 8, 5),
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            payment_status=OrderDelivery.PaymentStatus.CHARGED,
            charged_amount=Decimal('100.00'),
            marked_at=timezone.now(),
        )

        self.wallet = Wallet.objects.create(
            customer=self.customer_a,
            balance=Decimal('500.00'),
        )
        WalletTransaction.objects.create(
            wallet=self.wallet,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            amount=Decimal('500.00'),
            balance_after=Decimal('500.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        WalletTransaction.objects.create(
            wallet=self.wallet,
            type=WalletTransaction.Type.PAYMENT,
            direction=WalletTransaction.Direction.DEBIT,
            amount=Decimal('100.00'),
            balance_after=Decimal('400.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        WalletTransaction.objects.create(
            wallet=self.wallet,
            type=WalletTransaction.Type.RECHARGE,
            direction=WalletTransaction.Direction.CREDIT,
            amount=Decimal('500.00'),
            method=WalletTransaction.Method.BKASH,
            external_ref='pending-ref-001',
            status=WalletTransaction.Status.PENDING,
        )
        self.wallet.balance = Decimal('500.00')
        self.wallet.save(update_fields=['balance'])

        self.subscription_d = CustomerSubscription.objects.create(
            customer=self.customer_d,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_period_snapshot=self.meal.meal_period,
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date(2026, 8, 1),
        )
        self.sub_delivery = OrderDelivery.objects.create(
            subscription=self.subscription_d,
            service_date=date(2026, 8, 10),
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            marked_at=timezone.now(),
        )

        self.cancelled_subscription = CustomerSubscription.objects.create(
            customer=self.customer_b,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_period_snapshot=self.meal.meal_period,
            status=CustomerSubscription.Status.CANCELLED,
            started_on=date(2026, 6, 1),
            cancelled_at=timezone.now(),
            cancel_effective_on=date(2026, 6, 30),
        )

        self.list_url = reverse('web_customers:admin-customer-list')

    def _make_customer(
        self,
        suffix,
        *,
        email,
        phone,
        first_name,
        last_name,
        is_email_verified,
        is_active,
    ):
        user = User.objects.create_user(
            username=f'cust_{suffix}',
            email=email,
            password='StrongPassword123',
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
        )
        user.groups.add(self.customer_group)
        return CustomerProfile.objects.create(
            user=user,
            phone=phone,
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=is_email_verified,
        )

    def _create_active_order(self, customer):
        return Order.objects.create(
            customer=customer,
            meal=self.meal,
            meal_name_snapshot=self.meal.meal_name,
            meal_type_snapshot=self.meal.meal_type,
            meal_period_snapshot=self.meal.meal_period,
            total_price_snapshot=self.meal.total_price,
            per_meal_price_snapshot=Decimal('100.00'),
            order_status=Order.OrderStatus.ACTIVE,
            order_start_date=date(2026, 8, 1),
            order_end_date=date(2026, 8, 31),
            service_days_count=30,
            order_month='2026-08',
        )

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self, customer_profile):
        token = Token.objects.create(user=customer_profile.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_unauthenticated_list_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_cannot_list(self):
        self._auth_customer(self.customer_a)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_list_basic_fields(self):
        self._auth_admin()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 4)
        row = next(item for item in response.data['results'] if item['email'] == 'alice@example.com')
        self.assertEqual(row['name'], 'Alice Active')
        self.assertEqual(row['phone'], '+8801711111111')
        self.assertIsNone(row['profile_picture_url'])
        self.assertEqual(row['verification_status'], 'verified')
        self.assertEqual(row['account_status'], 'active')
        self.assertEqual(row['current_package']['package_name'], 'Regular Package')
        self.assertEqual(row['current_package']['remaining_meals'], 1)
        self.assertEqual(row['wallet_balance'], '500.00')
        self.assertEqual(str(row['public_id']), str(self.customer_a.public_id))

        sub_row = next(item for item in response.data['results'] if item['email'] == 'dave@example.com')
        self.assertEqual(sub_row['current_package']['subscription_public_id'], str(self.subscription_d.public_id))

    def test_search_by_email_and_phone(self):
        self._auth_admin()
        by_email = self.client.get(self.list_url, {'q': 'alice@'})
        self.assertEqual(by_email.status_code, status.HTTP_200_OK)
        self.assertEqual(by_email.data['count'], 1)
        by_phone = self.client.get(self.list_url, {'q': '1722222222'})
        self.assertEqual(by_phone.data['count'], 1)
        self.assertEqual(by_phone.data['results'][0]['email'], 'bob@example.com')
        by_e164 = self.client.get(self.list_url, {'q': '+8801722222222'})
        self.assertEqual(by_e164.data['count'], 1)
        self.assertEqual(by_e164.data['results'][0]['email'], 'bob@example.com')
        by_cc = self.client.get(self.list_url, {'q': '8801722222222'})
        self.assertEqual(by_cc.data['count'], 1)
        self.assertEqual(by_cc.data['results'][0]['email'], 'bob@example.com')

    def test_filters_active_verified_and_subscription(self):
        self._auth_admin()
        active = self.client.get(self.list_url, {'is_active': 'true'})
        emails = {r['email'] for r in active.data['results']}
        self.assertIn('alice@example.com', emails)
        self.assertNotIn('bob@example.com', emails)

        with_sub = self.client.get(self.list_url, {'has_active_subscription': 'true'})
        self.assertEqual(with_sub.data['count'], 1)
        self.assertEqual(with_sub.data['results'][0]['email'], 'dave@example.com')

        with_wallet = self.client.get(self.list_url, {'has_wallet': 'true'})
        self.assertEqual(with_wallet.data['count'], 1)

        pending_recharge = self.client.get(self.list_url, {'has_pending_recharge': 'true'})
        self.assertEqual(pending_recharge.data['count'], 1)
        self.assertEqual(pending_recharge.data['results'][0]['email'], 'alice@example.com')

        inactive_sub = self.client.get(self.list_url, {'inactive_subscription': 'true'})
        inactive_emails = {r['email'] for r in inactive_sub.data['results']}
        self.assertIn('bob@example.com', inactive_emails)
        self.assertNotIn('dave@example.com', inactive_emails)

        with_order = self.client.get(self.list_url, {'has_active_order': 'true'})
        self.assertEqual(with_order.data['count'], 1)
        self.assertEqual(with_order.data['results'][0]['email'], 'alice@example.com')

    def test_unknown_filter_rejected(self):
        self._auth_admin()
        response = self.client.get(self.list_url, {'foo': 'bar'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_detail_overview_lean_and_404(self):
        self._auth_admin()
        url = reverse(
            'web_customers:admin-customer-detail',
            kwargs={'public_id': self.customer_a.public_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['verification_status'], 'verified')
        summary = response.data['summary']
        self.assertEqual(summary['total_orders'], 1)
        self.assertEqual(summary['total_meals_delivered'], 1)
        self.assertEqual(summary['total_meal_offs'], 1)
        self.assertEqual(summary['total_wallet_spent'], '100.00')
        self.assertEqual(summary['customer_lifetime_value'], '100.00')
        self.assertEqual(summary['wallet_balance'], '500.00')
        self.assertTrue(summary['has_legacy_orders'])
        self.assertIsNotNone(response.data['active_order'])
        self.assertIn('pending_recharge_amount', response.data['wallet_summary'])
        self.assertEqual(response.data['wallet_summary']['pending_recharge_amount'], '500.00')
        self.assertEqual(len(response.data['addresses']), 1)
        self.assertNotIn('subscriptions', response.data)
        self.assertNotIn('meals', response.data)
        self.assertNotIn('wallet_transactions', response.data)
        self.assertNotIn('activity', response.data)

        missing = reverse(
            'web_customers:admin-customer-detail',
            kwargs={'public_id': uuid4()},
        )
        self.assertEqual(self.client.get(missing).status_code, status.HTTP_404_NOT_FOUND)

    def test_subscribed_customer_active_subscription(self):
        self._auth_admin()
        detail_url = reverse(
            'web_customers:admin-customer-detail',
            kwargs={'public_id': self.customer_d.public_id},
        )
        detail = self.client.get(detail_url)
        self.assertIsNotNone(detail.data['active_subscription'])
        self.assertEqual(
            detail.data['active_subscription']['subscription_public_id'],
            str(self.subscription_d.public_id),
        )

        action_url = reverse(
            'web_customers:admin-customer-active-subscription',
            kwargs={'public_id': self.customer_d.public_id},
        )
        action = self.client.get(action_url)
        self.assertEqual(action.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(action.data['active_subscription'])

    def test_active_subscription_empty_when_none(self):
        self._auth_admin()
        url = reverse(
            'web_customers:admin-customer-active-subscription',
            kwargs={'public_id': self.customer_c.public_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['active_subscription'])

    def test_subscription_history_and_meals_include_subscription_rows(self):
        self._auth_admin()
        pid = self.customer_d.public_id

        subs = self.client.get(
            reverse('web_customers:admin-customer-subscriptions', kwargs={'public_id': pid})
        )
        self.assertEqual(subs.status_code, status.HTTP_200_OK)
        self.assertEqual(subs.data['count'], 1)
        self.assertEqual(str(subs.data['results'][0]['public_id']), str(self.subscription_d.public_id))

        meals = self.client.get(
            reverse('web_customers:admin-customer-meals', kwargs={'public_id': pid})
        )
        self.assertEqual(meals.status_code, status.HTTP_200_OK)
        self.assertEqual(meals.data['count'], 1)
        self.assertEqual(
            meals.data['results'][0]['subscription_public_id'],
            str(self.subscription_d.public_id),
        )

    def test_wallet_overview_pending_and_totals(self):
        self._auth_admin()
        url = reverse(
            'web_customers:admin-customer-wallet-overview',
            kwargs={'public_id': self.customer_a.public_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        overview = response.data['wallet_overview']
        self.assertEqual(overview['available_balance'], '500.00')
        self.assertEqual(overview['pending_recharge_amount'], '500.00')
        self.assertEqual(overview['total_spent'], '100.00')
        self.assertEqual(overview['total_recharged'], '500.00')

    def test_history_scoped_and_wallet_empty(self):
        self._auth_admin()
        pid = self.customer_a.public_id
        other_pid = self.customer_c.public_id

        orders = self.client.get(
            reverse('web_customers:admin-customer-orders', kwargs={'public_id': pid})
        )
        self.assertEqual(orders.status_code, status.HTTP_200_OK)
        self.assertEqual(orders.data['count'], 1)
        self.assertIn('Deprecation', orders.headers)
        self.assertEqual(str(orders.data['results'][0]['public_id']), str(self.order_a.public_id))

        other_orders = self.client.get(
            reverse('web_customers:admin-customer-orders', kwargs={'public_id': other_pid})
        )
        self.assertEqual(other_orders.data['count'], 0)

        meals = self.client.get(
            reverse('web_customers:admin-customer-meals', kwargs={'public_id': pid}),
            {'meal_period': 'lunch'},
        )
        self.assertEqual(meals.status_code, status.HTTP_200_OK)
        self.assertTrue(all(r['meal_period'] == 'lunch' for r in meals.data['results']))

        meal_offs = self.client.get(
            reverse('web_customers:admin-customer-meal-offs', kwargs={'public_id': pid})
        )
        self.assertEqual(meal_offs.data['count'], 1)
        self.assertEqual(meal_offs.data['results'][0]['note'], 'Traveling')

        wallet = self.client.get(
            reverse(
                'web_customers:admin-customer-wallet-transactions',
                kwargs={'public_id': pid},
            )
        )
        self.assertEqual(wallet.status_code, status.HTTP_200_OK)
        self.assertEqual(wallet.data['count'], 3)

        empty_wallet = self.client.get(
            reverse(
                'web_customers:admin-customer-wallet-transactions',
                kwargs={'public_id': other_pid},
            )
        )
        self.assertEqual(empty_wallet.status_code, status.HTTP_200_OK)
        self.assertEqual(empty_wallet.data['count'], 0)

        activity = self.client.get(
            reverse('web_customers:admin-customer-activity', kwargs={'public_id': pid})
        )
        self.assertEqual(activity.status_code, status.HTTP_200_OK)
        event_types = {item['event_type'] for item in activity.data['results']}
        self.assertIn('order_created', event_types)
        self.assertIn('meal_skipped', event_types)
        self.assertIn('meal_delivered', event_types)
        self.assertIn('wallet_transaction_completed', event_types)
        self.assertNotIn('meal_off', event_types)

    def test_activity_confirmed_events_for_subscription_customer(self):
        self._auth_admin()
        url = reverse(
            'web_customers:admin-customer-activity',
            kwargs={'public_id': self.customer_d.public_id},
        )
        response = self.client.get(url)
        event_types = {item['event_type'] for item in response.data['results']}
        self.assertIn('subscription_created', event_types)
        self.assertIn('meal_delivered', event_types)

    def test_invalid_meal_filter_rejected(self):
        self._auth_admin()
        url = reverse(
            'web_customers:admin-customer-meals',
            kwargs={'public_id': self.customer_a.public_id},
        )
        response = self.client.get(url, {'meal_period': 'brunch'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_denied_admin_endpoints(self):
        self._auth_customer(self.customer_a)
        endpoints = [
            reverse('web_customers:admin-customer-list'),
            reverse(
                'web_customers:admin-customer-detail',
                kwargs={'public_id': self.customer_b.public_id},
            ),
            reverse(
                'web_customers:admin-customer-active-subscription',
                kwargs={'public_id': self.customer_b.public_id},
            ),
            reverse(
                'web_customers:admin-customer-subscriptions',
                kwargs={'public_id': self.customer_b.public_id},
            ),
            reverse(
                'web_customers:admin-customer-wallet-overview',
                kwargs={'public_id': self.customer_b.public_id},
            ),
            reverse(
                'web_customers:admin-customer-activity',
                kwargs={'public_id': self.customer_b.public_id},
            ),
        ]
        for url in endpoints:
            self.assertEqual(
                self.client.get(url).status_code,
                status.HTTP_403_FORBIDDEN,
                msg=f'Expected 403 for {url}',
            )

    def test_cancelled_subscription_customer_overview(self):
        self._auth_admin()
        url = reverse(
            'web_customers:admin-customer-detail',
            kwargs={'public_id': self.customer_b.public_id},
        )
        response = self.client.get(url)
        self.assertIsNone(response.data['active_subscription'])
        subs = self.client.get(
            reverse(
                'web_customers:admin-customer-subscriptions',
                kwargs={'public_id': self.customer_b.public_id},
            )
        )
        self.assertEqual(subs.data['count'], 1)
        self.assertEqual(subs.data['results'][0]['status'], 'cancelled')
