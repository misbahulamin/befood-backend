from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ledger import credit_admin_wallet, get_or_create_platform_wallet
from admin_wallet.services.operations import manual_deposit
from inventory.models import (
    InventoryAuditLog,
    InventoryItem,
    InventoryPurchase,
    InventoryStockMovement,
    InventoryUnit,
)
from inventory.services.items import create_item
from inventory.services.ledger import InsufficientStockError, inventory_value, ledger_sum
from inventory.services.operations import adjust_stock, issue_kitchen_usage, record_wastage
from inventory.services.purchasing import cancel_purchase, confirm_purchase, create_purchase
from inventory.services.queries import reconcile_items, report_rows
from inventory.services.units import convert_to_base, InventoryUnitError
from user_management.models import AdminProfile, CustomerProfile


@override_settings(
    MEDIA_ROOT='test_media_inventory',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class InventoryServiceTests(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='inv_admin',
            email='inv_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(Group.objects.get(name='ADMIN'))
        self.admin_profile = AdminProfile.objects.create(
            user=self.admin_user, is_verified=True
        )
        self.beef = create_item(
            name='Beef',
            default_unit=InventoryUnit.KG,
            category='meat',
            minimum_stock_level=Decimal('10'),
            created_by=self.admin_profile,
        )
        get_or_create_platform_wallet()
        manual_deposit(
            Decimal('200000.00'),
            reason='Seed',
            actor_admin=self.admin_profile,
        )

    def test_unit_conversion_and_reject_incompatible(self):
        self.assertEqual(
            convert_to_base(Decimal('500'), from_unit='g', base_unit='kg'),
            Decimal('0.500'),
        )
        with self.assertRaises(InventoryUnitError):
            convert_to_base(Decimal('2'), from_unit='piece', base_unit='kg')

    def test_additive_purchase_and_wac(self):
        p1 = create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('10'),
                    'unit': 'kg',
                    'line_total': Decimal('5000.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=True,
        )
        self.beef.refresh_from_db()
        self.assertEqual(p1.status, InventoryPurchase.Status.CONFIRMED)
        self.assertEqual(self.beef.quantity_on_hand, Decimal('10.000'))
        self.assertEqual(self.beef.average_unit_cost, Decimal('500.0000'))

        create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('20'),
                    'unit': 'kg',
                    'line_total': Decimal('11000.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=True,
        )
        self.beef.refresh_from_db()
        self.assertEqual(self.beef.quantity_on_hand, Decimal('30.000'))
        self.assertEqual(self.beef.average_unit_cost, Decimal('533.3333'))
        self.assertEqual(inventory_value(self.beef), Decimal('16000.00'))

    def test_negative_stock_rejected(self):
        create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('10'),
                    'unit': 'kg',
                    'line_total': Decimal('5000.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=True,
        )
        with self.assertRaises(InsufficientStockError):
            issue_kitchen_usage(
                item=self.beef,
                quantity=Decimal('15'),
                issued_by=self.admin_profile,
            )
        self.beef.refresh_from_db()
        self.assertEqual(self.beef.quantity_on_hand, Decimal('10.000'))

    def test_wallet_debit_atomic_and_insufficient_rolls_back(self):
        wallet = get_or_create_platform_wallet()
        wallet.balance = Decimal('1000.00')
        wallet.save(update_fields=['balance', 'updated_at'])

        purchase = create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('50'),
                    'unit': 'kg',
                    'line_total': Decimal('25000.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=False,
        )
        with self.assertRaises(Exception) as ctx:
            confirm_purchase(purchase, actor_admin=self.admin_profile)
        self.assertEqual(ctx.exception.code, 'INSUFFICIENT_WALLET_BALANCE')
        purchase.refresh_from_db()
        self.beef.refresh_from_db()
        self.assertEqual(purchase.status, InventoryPurchase.Status.DRAFT)
        self.assertEqual(self.beef.quantity_on_hand, Decimal('0.000'))
        self.assertEqual(get_or_create_platform_wallet().balance, Decimal('1000.00'))

    def test_idempotent_confirm_and_cancel_rules(self):
        purchase = create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('50'),
                    'unit': 'kg',
                    'line_total': Decimal('25000.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=True,
        )
        bal_after = get_or_create_platform_wallet().balance
        again = confirm_purchase(purchase, actor_admin=self.admin_profile)
        self.assertEqual(again.status, InventoryPurchase.Status.CONFIRMED)
        self.assertEqual(get_or_create_platform_wallet().balance, bal_after)
        self.assertEqual(
            AdminWalletTransaction.objects.filter(
                type=AdminWalletTransaction.Type.INVENTORY_PURCHASE,
                idempotency_key=f'inventory-purchase:{purchase.public_id}',
            ).count(),
            1,
        )

        issue_kitchen_usage(
            item=self.beef,
            quantity=Decimal('12'),
            purpose='Lunch',
            issued_by=self.admin_profile,
        )
        with self.assertRaises(Exception) as ctx:
            cancel_purchase(purchase, actor_admin=self.admin_profile)
        self.assertEqual(ctx.exception.code, 'CANCEL_BLOCKED_STOCK_CONSUMED')

        # Top up enough to allow cancel after putting stock back via adjustment
        adjust_stock(
            item=self.beef,
            quantity_delta=Decimal('12'),
            reason='Return unused',
            adjusted_by=self.admin_profile,
        )
        cancelled = cancel_purchase(purchase, actor_admin=self.admin_profile)
        self.assertEqual(cancelled.status, InventoryPurchase.Status.CANCELLED)
        self.beef.refresh_from_db()
        self.assertEqual(self.beef.quantity_on_hand, Decimal('0.000'))

    def test_usage_wastage_adjustment_audit_and_reconcile(self):
        create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('55'),
                    'unit': 'kg',
                    'line_total': Decimal('27500.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=True,
        )
        issue_kitchen_usage(
            item=self.beef,
            quantity=Decimal('12'),
            purpose='Dinner',
            issued_by=self.admin_profile,
        )
        record_wastage(
            item=self.beef,
            quantity=Decimal('3'),
            reason='Spoilage',
            recorded_by=self.admin_profile,
        )
        adjust_stock(
            item=self.beef,
            quantity_delta=Decimal('2'),
            reason='Count fix',
            adjusted_by=self.admin_profile,
        )
        self.beef.refresh_from_db()
        self.assertEqual(self.beef.quantity_on_hand, Decimal('42.000'))
        self.assertEqual(ledger_sum(self.beef), Decimal('42.000'))
        self.assertEqual(reconcile_items(), [])
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.STOCK_USED
            ).exists()
        )
        self.assertTrue(
            InventoryStockMovement.objects.filter(
                item=self.beef,
                type=InventoryStockMovement.Type.WASTAGE,
            ).exists()
        )


@override_settings(
    MEDIA_ROOT='test_media_inventory',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class InventoryAPITests(APITestCase):
    def setUp(self):
        Group.objects.get_or_create(name='ADMIN')
        Group.objects.get_or_create(name='CUSTOMER')
        self.admin_user = User.objects.create_user(
            username='inv_api_admin',
            email='inv_api_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(Group.objects.get(name='ADMIN'))
        self.admin_profile = AdminProfile.objects.create(
            user=self.admin_user, is_verified=True
        )
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='inv_customer',
            email='inv_customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.customer_user.groups.add(Group.objects.get(name='CUSTOMER'))
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1700000001',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.beef = create_item(
            name='Chicken',
            default_unit=InventoryUnit.KG,
            category='meat',
            minimum_stock_level=Decimal('5'),
            created_by=self.admin_profile,
        )
        get_or_create_platform_wallet()
        credit_admin_wallet(
            Decimal('100000.00'),
            type=AdminWalletTransaction.Type.OTHER_INCOME,
            source='Seed',
        )

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def test_permissions(self):
        url = reverse('web_inventory:dashboard')
        res = self.client.get(url)
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        self._auth_customer()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self._auth_admin()
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('total_inventory_items', res.data)

    def test_purchase_history_filters_and_usage(self):
        self._auth_admin()
        create_res = self.client.post(
            reverse('web_inventory:purchases'),
            {
                'confirm': True,
                'supplier': 'Local Market',
                'lines': [
                    {
                        'item_public_id': str(self.beef.public_id),
                        'quantity': '20',
                        'unit': 'kg',
                        'line_total': '10000.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data['status'], 'confirmed')
        self.assertIsNotNone(create_res.data['wallet_transaction_public_id'])

        hist = self.client.get(
            reverse('web_inventory:purchase-history'),
            {'item': str(self.beef.public_id), 'supplier': 'Local'},
        )
        self.assertEqual(hist.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(hist.data['count'], 1)

        bad = self.client.get(
            reverse('web_inventory:purchase-history'),
            {'unknown_filter': 'x'},
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad.data.get('error_code'), 'UNSUPPORTED_FILTER')

        issue = self.client.post(
            reverse('web_inventory:stock-issues'),
            {
                'item_public_id': str(self.beef.public_id),
                'quantity': '5',
                'purpose': 'Lunch cook',
            },
            format='json',
        )
        self.assertEqual(issue.status_code, status.HTTP_201_CREATED)

        usage = self.client.get(
            reverse('web_inventory:usage-history'),
            {'item': str(self.beef.public_id)},
        )
        self.assertEqual(usage.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(usage.data['count'], 1)

    def test_reports_allowlist_and_invoice_validation(self):
        self._auth_admin()
        ok = self.client.get(reverse('web_inventory:reports', kwargs={'report_key': 'stock_valuation'}))
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.data['report_key'], 'stock_valuation')

        bad = self.client.get(
            reverse('web_inventory:reports', kwargs={'report_key': 'not_a_report'})
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        purchase = create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('5'),
                    'unit': 'kg',
                    'line_total': Decimal('2500.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=False,
        )
        bad_file = SimpleUploadedFile(
            'evil.exe', b'MZfake', content_type='application/octet-stream'
        )
        inv = self.client.post(
            reverse(
                'web_inventory:purchase-invoice',
                kwargs={'public_id': purchase.public_id},
            ),
            {'invoice': bad_file},
            format='multipart',
        )
        self.assertEqual(inv.status_code, status.HTTP_400_BAD_REQUEST)

        good = SimpleUploadedFile(
            'receipt.png',
            b'\x89PNG\r\n\x1a\n' + b'\x00' * 20,
            content_type='image/png',
        )
        inv_ok = self.client.post(
            reverse(
                'web_inventory:purchase-invoice',
                kwargs={'public_id': purchase.public_id},
            ),
            {'invoice': good},
            format='multipart',
        )
        self.assertEqual(inv_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(inv_ok.data['has_invoice'])

        # report_rows helper smoke
        self.assertIsInstance(report_rows('admin_activity'), list)

    def test_duplicate_item_name_and_insufficient_stock_codes(self):
        self._auth_admin()
        dup = self.client.post(
            reverse('web_inventory:items'),
            {
                'name': 'Chicken',
                'default_unit': 'kg',
                'category': 'meat',
                'status': 'active',
            },
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(dup.data.get('error_code'), 'DUPLICATE_ITEM_NAME')

        create_purchase(
            lines=[
                {
                    'item': self.beef,
                    'quantity': Decimal('2'),
                    'unit': 'kg',
                    'line_total': Decimal('1000.00'),
                }
            ],
            actor_admin=self.admin_profile,
            confirm=True,
        )
        over = self.client.post(
            reverse('web_inventory:stock-issues'),
            {
                'item_public_id': str(self.beef.public_id),
                'quantity': '10',
                'unit': 'kg',
                'purpose': 'Too much',
            },
            format='json',
        )
        self.assertEqual(over.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(over.data.get('error_code'), 'INSUFFICIENT_STOCK')
