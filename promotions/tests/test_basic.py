from django.test import SimpleTestCase


class PromotionsImportTest(SimpleTestCase):
    def test_import(self):
        __import__('promotions')
