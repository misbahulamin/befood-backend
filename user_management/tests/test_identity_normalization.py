"""Unit tests for identity normalization helpers."""

from django.test import SimpleTestCase

from user_management.services.identity_normalization import (
    PhoneNormalizationError,
    normalize_email,
    normalize_phone_number,
    phone_to_sms_dial,
)


class NormalizePhoneNumberTests(SimpleTestCase):
    def test_national_with_leading_zero(self):
        self.assertEqual(normalize_phone_number('01712345678'), '1712345678')

    def test_e164(self):
        self.assertEqual(normalize_phone_number('+8801712345678'), '1712345678')

    def test_country_code_without_plus(self):
        self.assertEqual(normalize_phone_number('8801712345678'), '1712345678')

    def test_spaced_and_dashed(self):
        self.assertEqual(normalize_phone_number('+880 1712-345678'), '1712345678')

    def test_already_canonical(self):
        self.assertEqual(normalize_phone_number('1712345678'), '1712345678')

    def test_invalid_rejected(self):
        with self.assertRaises(PhoneNormalizationError):
            normalize_phone_number('12345')
        with self.assertRaises(PhoneNormalizationError):
            normalize_phone_number('+441234567890')
        with self.assertRaises(PhoneNormalizationError):
            normalize_phone_number('')

    def test_sms_dial_format(self):
        self.assertEqual(phone_to_sms_dial('01712345678'), '8801712345678')


class NormalizeEmailTests(SimpleTestCase):
    def test_lower_and_strip(self):
        self.assertEqual(normalize_email('  Test@Example.COM '), 'test@example.com')

    def test_empty(self):
        self.assertEqual(normalize_email(None), '')
        self.assertEqual(normalize_email(''), '')
