from django.test import SimpleTestCase


class DeliveryImportTest(SimpleTestCase):
    def test_import(self):
        __import__('delivery')
