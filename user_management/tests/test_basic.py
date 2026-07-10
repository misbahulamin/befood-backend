from django.test import SimpleTestCase


class UserManagementImportTest(SimpleTestCase):
    def test_import(self):
        __import__('user_management')
