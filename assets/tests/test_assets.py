from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import resolve
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from business.models import BusinessProfile, Outlet
from user_management.models import AdminProfile, CustomerProfile

from assets.api.views import AssetCategoryViewSet, PermanentAssetViewSet
from assets.models import AssetCategory, PermanentAsset
from assets.services import soft_retire_asset

User = get_user_model()


def _category(**overrides) -> AssetCategory:
    defaults = {
        'name': 'Test Category',
        'description': 'For tests',
        'is_active': True,
    }
    defaults.update(overrides)
    # Unique name if colliding with seeds
    if AssetCategory.objects.filter(name=defaults['name']).exists():
        defaults['name'] = f"{defaults['name']}-{AssetCategory.objects.count()}"
    cat = AssetCategory(**defaults)
    cat.full_clean()
    cat.save()
    return cat


def _asset(category=None, **overrides) -> PermanentAsset:
    if category is None:
        category = _category()
    defaults = {
        'name': 'Walk-in Refrigerator',
        'category': category,
        'asset_tag': f'TAG-{PermanentAsset.objects.count() + 1}',
        'status': PermanentAsset.Status.IN_SERVICE,
        'quantity': 1,
        'is_active': True,
    }
    defaults.update(overrides)
    asset = PermanentAsset(**defaults)
    asset.full_clean()
    asset.save()
    return asset


class PermanentAssetModelTests(TestCase):
    def test_rejects_quantity_below_one(self):
        cat = _category(name='Qty Cat')
        asset = PermanentAsset(
            name='Bad',
            category=cat,
            asset_tag='BAD-Q',
            quantity=0,
        )
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn('quantity', ctx.exception.message_dict)

    def test_rejects_warranty_before_purchase(self):
        cat = _category(name='Warranty Cat')
        asset = PermanentAsset(
            name='Burner',
            category=cat,
            asset_tag='WAR-1',
            purchase_date=date(2026, 1, 10),
            warranty_until=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn('warranty_until', ctx.exception.message_dict)

    def test_rejects_invalid_status(self):
        cat = _category(name='Status Cat')
        asset = PermanentAsset(
            name='X',
            category=cat,
            asset_tag='ST-1',
            status='broken',
        )
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn('status', ctx.exception.message_dict)

    def test_seed_categories_exist(self):
        for name in (
            'Kitchen Equipment',
            'Furniture',
            'Lighting',
            'Computer Equipment',
            'Other',
        ):
            self.assertTrue(
                AssetCategory.objects.filter(name=name, is_active=True).exists(),
                msg=f'Missing seed category: {name}',
            )


@override_settings(ROOT_URLCONF='core.urls')
class AssetCategoryAdminAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='asset-admin',
            email='asset-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.unverified_user = User.objects.create_user(
            username='asset-unverified',
            email='asset-unverified@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.unverified_user, is_verified=False)
        self.unverified_user.groups.add(self.admin_group)
        self.unverified_token = Token.objects.create(user=self.unverified_user)

        self.customer_user = User.objects.create_user(
            username='asset-customer',
            email='asset-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345601',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.list_url = reverse('assets:categories-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _auth_unverified(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Token {self.unverified_token.key}'
        )

    def _detail_url(self, public_id):
        return reverse(
            'assets:categories-detail',
            kwargs={'public_id': public_id},
        )

    def test_url_resolution_categories_before_asset_detail(self):
        match = resolve('/assets/categories/')
        self.assertEqual(match.func.cls, AssetCategoryViewSet)
        list_match = resolve('/assets/')
        self.assertEqual(list_match.func.cls, PermanentAssetViewSet)

    def test_anonymous_denied(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_denied(self):
        self._auth_customer()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        create = self.client.post(
            self.list_url,
            {'name': 'Nope'},
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_admin_denied(self):
        self._auth_unverified()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_category_crud(self):
        self._auth_admin()
        create_resp = self.client.post(
            self.list_url,
            {
                'name': 'Large Cookware',
                'description': 'Korai and similar',
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        public_id = create_resp.data['public_id']
        self.assertEqual(create_resp.data['name'], 'Large Cookware')

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in list_resp.data['results']]
        self.assertIn('Large Cookware', names)

        detail = self.client.get(self._detail_url(public_id))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        patch = self.client.patch(
            self._detail_url(public_id),
            {'description': 'Updated'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['description'], 'Updated')

        delete = self.client.delete(self._detail_url(public_id))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        cat = AssetCategory.objects.get(public_id=public_id)
        self.assertFalse(cat.is_active)

        # Default list hides inactive
        list_after = self.client.get(self.list_url)
        names_after = [row['name'] for row in list_after.data['results']]
        self.assertNotIn('Large Cookware', names_after)

    def test_duplicate_category_name_rejected(self):
        self._auth_admin()
        self.client.post(
            self.list_url,
            {'name': 'Unique Gear'},
            format='json',
        )
        dup = self.client.post(
            self.list_url,
            {'name': 'Unique Gear'},
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(ROOT_URLCONF='core.urls')
class PermanentAssetAdminAPITests(APITestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')

        self.admin_user = User.objects.create_user(
            username='pam-admin',
            email='pam-admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_user.groups.add(self.admin_group)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.customer_user = User.objects.create_user(
            username='pam-customer',
            email='pam-customer@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1712345602',
            occupation='student',
            is_bachelor=True,
            is_email_verified=True,
        )
        self.customer_user.groups.add(self.customer_group)
        self.customer_token = Token.objects.create(user=self.customer_user)

        self.kitchen = AssetCategory.objects.get(name='Kitchen Equipment')
        self.furniture = AssetCategory.objects.get(name='Furniture')

        business = BusinessProfile.objects.create(name='Befood Test')
        self.outlet = Outlet.objects.create(
            business=business,
            name='Main Kitchen',
            address='Dhaka',
            is_active=True,
        )

        self.list_url = reverse('assets:assets-list')

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def _detail_url(self, public_id):
        return reverse('assets:assets-detail', kwargs={'public_id': public_id})

    def test_anonymous_and_customer_denied_on_assets(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self._auth_customer()
        denied = self.client.get(self.list_url)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        create = self.client.post(
            self.list_url,
            {
                'name': 'Nope',
                'category_public_id': str(self.kitchen.public_id),
                'asset_tag': 'NOPE-1',
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_refrigerator_style_asset(self):
        self._auth_admin()
        resp = self.client.post(
            self.list_url,
            {
                'name': 'Walk-in Refrigerator',
                'category_public_id': str(self.kitchen.public_id),
                'asset_tag': 'KE-REF-001',
                'status': 'in_service',
                'quantity': 1,
                'brand': 'Samsung',
                'outlet_id': self.outlet.id,
                'purchase_cost': '45000.00',
                'currency': 'BDT',
                'purchase_date': '2026-01-15',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIn('public_id', resp.data)
        self.assertEqual(resp.data['asset_tag'], 'KE-REF-001')
        self.assertEqual(resp.data['category']['name'], 'Kitchen Equipment')
        self.assertEqual(resp.data['outlet']['id'], self.outlet.id)
        self.assertEqual(resp.data['purchase_cost'], '45000.00')
        self.assertNotIn('id', resp.data)

        detail = self.client.get(self._detail_url(resp.data['public_id']))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_batch_quantity_chairs(self):
        self._auth_admin()
        resp = self.client.post(
            self.list_url,
            {
                'name': 'Dining Chairs',
                'category_public_id': str(self.furniture.public_id),
                'asset_tag': 'FU-CHAIR-BATCH-1',
                'quantity': 12,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['quantity'], 12)

    def test_duplicate_asset_tag_rejected(self):
        self._auth_admin()
        payload = {
            'name': 'Gas Burner A',
            'category_public_id': str(self.kitchen.public_id),
            'asset_tag': 'KE-BURN-1',
        }
        first = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            self.list_url,
            {**payload, 'name': 'Gas Burner B'},
            format='json',
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_status_and_quantity_rejected(self):
        self._auth_admin()
        bad_status = self.client.post(
            self.list_url,
            {
                'name': 'X',
                'category_public_id': str(self.kitchen.public_id),
                'asset_tag': 'BAD-ST',
                'status': 'broken',
            },
            format='json',
        )
        self.assertEqual(bad_status.status_code, status.HTTP_400_BAD_REQUEST)

        bad_qty = self.client.post(
            self.list_url,
            {
                'name': 'Y',
                'category_public_id': str(self.kitchen.public_id),
                'asset_tag': 'BAD-QTY',
                'quantity': 0,
            },
            format='json',
        )
        self.assertEqual(bad_qty.status_code, status.HTTP_400_BAD_REQUEST)

    def test_warranty_before_purchase_rejected(self):
        self._auth_admin()
        resp = self.client.post(
            self.list_url,
            {
                'name': 'Rice Cooker',
                'category_public_id': str(self.kitchen.public_id),
                'asset_tag': 'KE-RC-1',
                'purchase_date': '2026-06-01',
                'warranty_until': '2026-01-01',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_search_and_default_excludes_inactive(self):
        self._auth_admin()
        active = _asset(
            category=self.kitchen,
            name='Active Stove',
            asset_tag='KE-STOVE-1',
            status=PermanentAsset.Status.IN_SERVICE,
        )
        inactive = _asset(
            category=self.kitchen,
            name='Old Light',
            asset_tag='LI-OLD-1',
            is_active=False,
            status=PermanentAsset.Status.RETIRED,
        )

        by_status = self.client.get(self.list_url, {'status': 'in_service'})
        self.assertEqual(by_status.status_code, status.HTTP_200_OK)
        tags = [r['asset_tag'] for r in by_status.data['results']]
        self.assertIn('KE-STOVE-1', tags)

        by_cat = self.client.get(
            self.list_url,
            {'category_public_id': str(self.kitchen.public_id)},
        )
        self.assertEqual(by_cat.status_code, status.HTTP_200_OK)

        search = self.client.get(self.list_url, {'search': 'KE-STOVE-1'})
        self.assertEqual(len(search.data['results']), 1)
        self.assertEqual(search.data['results'][0]['public_id'], str(active.public_id))

        default_list = self.client.get(self.list_url)
        default_tags = [r['asset_tag'] for r in default_list.data['results']]
        self.assertNotIn(inactive.asset_tag, default_tags)

        with_inactive = self.client.get(
            self.list_url,
            {'include_inactive': 'true'},
        )
        inactive_tags = [r['asset_tag'] for r in with_inactive.data['results']]
        self.assertIn(inactive.asset_tag, inactive_tags)

        page = self.client.get(self.list_url, {'page_size': 1})
        self.assertEqual(page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(page.data['results']), 1)
        self.assertIn('count', page.data)

    def test_patch_status_and_delete_soft_retires(self):
        self._auth_admin()
        create = self.client.post(
            self.list_url,
            {
                'name': 'Gas Burner',
                'category_public_id': str(self.kitchen.public_id),
                'asset_tag': 'KE-GAS-99',
                'status': 'in_service',
            },
            format='json',
        )
        public_id = create.data['public_id']

        patch = self.client.patch(
            self._detail_url(public_id),
            {'status': 'under_maintenance'},
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['status'], 'under_maintenance')

        delete = self.client.delete(self._detail_url(public_id))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        asset = PermanentAsset.objects.get(public_id=public_id)
        self.assertFalse(asset.is_active)
        self.assertEqual(asset.status, PermanentAsset.Status.RETIRED)

    def test_soft_retire_service_preserves_disposed(self):
        asset = _asset(
            category=self.kitchen,
            asset_tag='DISP-1',
            status=PermanentAsset.Status.DISPOSED,
        )
        soft_retire_asset(asset)
        asset.refresh_from_db()
        self.assertFalse(asset.is_active)
        self.assertEqual(asset.status, PermanentAsset.Status.DISPOSED)

    def test_missing_category_rejected(self):
        self._auth_admin()
        resp = self.client.post(
            self.list_url,
            {'name': 'No Cat', 'asset_tag': 'NC-1'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
