from django.test import SimpleTestCase


class PaymentsImportTest(SimpleTestCase):
    def test_import(self):
        __import__('payments')
