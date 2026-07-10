from django.test import SimpleTestCase


class BusinessImportTest(SimpleTestCase):
    def test_import(self):
        __import__('business')
