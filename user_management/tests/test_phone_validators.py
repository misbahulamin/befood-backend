from django.test import SimpleTestCase

from user_management.validators import (
    format_bd_phone_e164,
    format_bd_phone_readable,
    normalize_phone_search_term,
)


class FormatBdPhoneE164Tests(SimpleTestCase):
    def test_national_ten_digits(self):
        self.assertEqual(format_bd_phone_e164('1894126298'), '+8801894126298')

    def test_empty_and_none(self):
        self.assertIsNone(format_bd_phone_e164(None))
        self.assertIsNone(format_bd_phone_e164(''))
        self.assertIsNone(format_bd_phone_e164('   '))

    def test_already_e164(self):
        self.assertEqual(format_bd_phone_e164('+8801894126298'), '+8801894126298')

    def test_thirteen_digit_country_code_without_plus(self):
        self.assertEqual(format_bd_phone_e164('8801894126298'), '+8801894126298')

    def test_malformed_passthrough(self):
        self.assertEqual(format_bd_phone_e164('bad-phone'), 'bad-phone')


class FormatBdPhoneReadableTests(SimpleTestCase):
    def test_from_national(self):
        self.assertEqual(format_bd_phone_readable('1894126298'), '+880-1894-126298')

    def test_from_e164(self):
        self.assertEqual(format_bd_phone_readable('+8801894126298'), '+880-1894-126298')

    def test_empty(self):
        self.assertIsNone(format_bd_phone_readable(None))
        self.assertIsNone(format_bd_phone_readable(''))

    def test_malformed_falls_back_to_e164_or_raw(self):
        self.assertEqual(format_bd_phone_readable('bad-phone'), 'bad-phone')


class NormalizePhoneSearchTermTests(SimpleTestCase):
    def test_strips_e164_prefix(self):
        self.assertEqual(normalize_phone_search_term('+8801894126298'), '1894126298')

    def test_strips_country_code_without_plus(self):
        self.assertEqual(normalize_phone_search_term('8801894126298'), '1894126298')

    def test_passthrough_national(self):
        self.assertEqual(normalize_phone_search_term('1894126298'), '1894126298')
