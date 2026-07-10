from django.test import SimpleTestCase


class NotificationsImportTest(SimpleTestCase):
    def test_import(self):
        __import__('notifications')
