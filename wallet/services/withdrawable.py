"""Shared maximum-withdrawable math for dual-bucket wallets."""

from decimal import Decimal


def compute_maximum_withdrawable(
    recharge_balance: Decimal,
    meal_stop_threshold: Decimal,
    *,
    has_active_subscription: bool = True,
    finalized_meal_liability: Decimal | None = None,
) -> Decimal:
    """
    Return maximum withdrawable from recharge, quantized to 2 dp.

    - Active subscriber: ``max(0, recharge_balance - meal_stop_threshold)``
    - No active subscription: ``max(0, recharge_balance - finalized_meal_liability)``

    Commission balance never contributes. Pending withdraw already reduced
    ``recharge_balance`` and is not reserved again.
    """
    if has_active_subscription:
        reserve = Decimal(meal_stop_threshold)
    else:
        reserve = Decimal(finalized_meal_liability or 0)
    headroom = Decimal(recharge_balance) - reserve
    if headroom <= 0:
        return Decimal('0.00')
    return headroom.quantize(Decimal('0.01'))
