from django.test import TestCase
from orders.services.order_status import ALLOWED_TRANSITIONS


class OrderWorkflowTest(TestCase):
    def test_allowed_map_includes_cancel_from_pending_and_confirmed(self):
        self.assertIn('cancelled', ALLOWED_TRANSITIONS['pending'])
        self.assertIn('cancelled', ALLOWED_TRANSITIONS['confirmed'])
