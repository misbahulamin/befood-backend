from django.db.models import Q
from django.test import SimpleTestCase

from user_management.services.admin_people_search import (
    build_customer_people_q,
    build_subscription_people_q,
    looks_like_uuid,
)


class LooksLikeUuidTests(SimpleTestCase):
    def test_canonical_uuid(self):
        self.assertTrue(looks_like_uuid('f4488b9b-49ce-440f-b3bc-645f3655b3a8'))

    def test_rejects_short_hex(self):
        self.assertFalse(looks_like_uuid('645f3655b3a8'))

    def test_rejects_phone_like(self):
        self.assertFalse(looks_like_uuid('1894126298'))

    def test_rejects_empty(self):
        self.assertFalse(looks_like_uuid(''))
        self.assertFalse(looks_like_uuid(None))


class BuildCustomerPeopleQTests(SimpleTestCase):
    def test_empty_q_is_unrestricted(self):
        self.assertEqual(build_customer_people_q(''), Q())
        self.assertEqual(build_customer_people_q('   '), Q())

    def test_email_and_name_fields(self):
        q = build_customer_people_q('rahim')
        children = q.children
        keys = {child[0] for child in children if isinstance(child, tuple)}
        self.assertIn('user__email__icontains', keys)
        self.assertIn('user__first_name__icontains', keys)
        self.assertIn('user__last_name__icontains', keys)
        self.assertIn('user__username__icontains', keys)

    def test_phone_normalization_path(self):
        q = build_customer_people_q('+8801894126298')
        self.assertIn(('phone__icontains', '1894126298'), q.children)

    def test_prefix_rewrites_fields(self):
        q = build_customer_people_q('a@b.com', customer_prefix='wallet__customer__')
        keys = {child[0] for child in q.children if isinstance(child, tuple)}
        self.assertIn('wallet__customer__user__email__icontains', keys)
        self.assertNotIn('user__email__icontains', keys)

    def test_canonical_uuid_adds_public_id(self):
        pid = 'f4488b9b-49ce-440f-b3bc-645f3655b3a8'
        q = build_customer_people_q(pid)
        self.assertIn(('public_id', pid), q.children)

    def test_short_hex_skips_public_id(self):
        q = build_customer_people_q('645f3655b3a8')
        keys = {child[0] for child in q.children if isinstance(child, tuple)}
        self.assertNotIn('public_id', keys)


class BuildSubscriptionPeopleQTests(SimpleTestCase):
    def test_includes_customer_prefix_and_subscription_public_id(self):
        pid = 'eed022ef-7b63-40ff-ada4-057a95a72290'
        q = build_subscription_people_q(pid)
        keys = {child[0] for child in q.children if isinstance(child, tuple)}
        # Nested OR from build_customer_people_q is a Q child; also top-level public_id.
        self.assertTrue(
            any(isinstance(child, Q) for child in q.children)
            or 'customer__user__email__icontains' in keys
        )
        self.assertIn(('public_id', pid), q.children)


class AdminPeopleSearchImportSmokeTests(SimpleTestCase):
    def test_orders_filters_and_wallet_web_views_import(self):
        import orders.filters  # noqa: F401
        import wallet.api.web_views  # noqa: F401

        self.assertTrue(hasattr(orders.filters, 'CustomerSubscriptionFilter'))
        self.assertTrue(hasattr(wallet.api.web_views, 'AdminFundingRequestViewSet'))
