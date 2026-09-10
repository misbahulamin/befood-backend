"""Unit tests for shared one-meal calculate_meal_price helper."""

from decimal import Decimal

from django.test import TestCase

from meals.services.pricing import calculate_meal_price


class CalculateMealPriceTests(TestCase):
    def test_subscriber_worked_example_20_percent(self):
        priced = calculate_meal_price(
            Decimal('100'),
            Decimal('10'),
            Decimal('20'),
        )
        self.assertEqual(priced['profit_amount'], '20.00')
        self.assertEqual(priced['final_price'], '130.00')
        self.assertEqual(priced['ingredient_cost'], '100.00')
        self.assertEqual(priced['operational_cost'], '10.00')
        self.assertEqual(priced['profit_percent'], '20.00')

    def test_instant_worked_example_70_percent(self):
        priced = calculate_meal_price(
            Decimal('100'),
            Decimal('10'),
            Decimal('70'),
        )
        self.assertEqual(priced['profit_amount'], '70.00')
        self.assertEqual(priced['final_price'], '180.00')

    def test_published_menu_worked_example(self):
        subscriber = calculate_meal_price(
            Decimal('48.15'),
            Decimal('4.13'),
            Decimal('14.45'),
        )
        self.assertEqual(subscriber['profit_amount'], '6.96')
        self.assertEqual(subscriber['final_price'], '59.24')

        instant = calculate_meal_price(
            Decimal('48.15'),
            Decimal('4.13'),
            Decimal('70.00'),
        )
        # 48.15 × 70% = 33.705 → ROUND_HALF_UP → 33.71; final 85.99
        self.assertEqual(instant['profit_amount'], '33.71')
        self.assertEqual(instant['final_price'], '85.99')
