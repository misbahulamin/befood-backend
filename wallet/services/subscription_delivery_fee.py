from decimal import Decimal


class SubscriptionDeliveryFeeError(Exception):
    """Invalid inputs for subscription delivery-fee calculation."""

    def __init__(self, message: str, *, code: str = 'INVALID_QUANTITY'):
        super().__init__(message)
        self.code = code


SINGLE_PERIOD_FEE = Decimal('200.00')
BOTH_FEE_1_3 = Decimal('400.00')
BOTH_FEE_4_5 = Decimal('350.00')
BOTH_FEE_6_PLUS = Decimal('300.00')

FEE_RULE_SINGLE = 'single_period'
FEE_RULE_BOTH_1_3 = 'both_q_1_3'
FEE_RULE_BOTH_4_5 = 'both_q_4_5'
FEE_RULE_BOTH_6_PLUS = 'both_q_6_plus'

SUPPORTED_PREFERENCES = frozenset({'lunch', 'dinner', 'both'})


def normalize_quantity(value) -> int:
    """Return a positive integer quantity (min 1)."""
    try:
        qty = int(value)
    except (TypeError, ValueError) as exc:
        raise SubscriptionDeliveryFeeError(
            'quantity must be a positive integer.',
            code='INVALID_QUANTITY',
        ) from exc
    if qty < 1:
        raise SubscriptionDeliveryFeeError(
            'quantity must be at least 1.',
            code='INVALID_QUANTITY',
        )
    return qty


def calculate_subscription_delivery_fee(meal_preference: str, quantity) -> dict:
    """
    Canonical monthly delivery fee from preference + quantity.

    Tiers (non-overlapping; quantity 3 is top of first both tier):
      lunch | dinner → 200
      both, 1–3 → 400
      both, 4–5 → 350
      both, 6+ → 300
    """
    preference = (meal_preference or '').strip().lower()
    if preference not in SUPPORTED_PREFERENCES:
        raise SubscriptionDeliveryFeeError(
            'meal_preference must be lunch, dinner, or both.',
            code='INVALID_MEAL_PREFERENCE',
        )
    qty = normalize_quantity(quantity)

    if preference in ('lunch', 'dinner'):
        amount = SINGLE_PERIOD_FEE
        rule = FEE_RULE_SINGLE
    elif qty <= 3:
        amount = BOTH_FEE_1_3
        rule = FEE_RULE_BOTH_1_3
    elif qty <= 5:
        amount = BOTH_FEE_4_5
        rule = FEE_RULE_BOTH_4_5
    else:
        amount = BOTH_FEE_6_PLUS
        rule = FEE_RULE_BOTH_6_PLUS

    return {
        'meal_period': preference,
        'quantity': qty,
        'amount': amount,
        'fee_rule_code': rule,
    }


def format_fee_summary(result: dict) -> dict:
    """API-facing fee summary (decimal string amount)."""
    amount = result['amount']
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return {
        'meal_period': result['meal_period'],
        'quantity': result['quantity'],
        'monthly_delivery_fee': f'{amount.quantize(Decimal("0.01")):.2f}',
        'fee_rule_code': result['fee_rule_code'],
    }
