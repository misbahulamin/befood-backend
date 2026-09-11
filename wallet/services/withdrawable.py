"""Shared maximum-withdrawable math for dual-bucket wallets."""

from decimal import Decimal


def compute_maximum_withdrawable(
    recharge_balance: Decimal,
    meal_stop_threshold: Decimal,
) -> Decimal:
    """
    Return max(0, recharge_balance - meal_stop_threshold) quantized to 2 dp.

    Commission balance never contributes. Meal-stop floor is preserved on the
    recharge bucket so withdraw cannot empty funds needed for meal service.
    """
    headroom = Decimal(recharge_balance) - Decimal(meal_stop_threshold)
    if headroom <= 0:
        return Decimal('0.00')
    return headroom.quantize(Decimal('0.01'))
