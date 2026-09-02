from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from orders.models import OrderWalletSettings


def get_order_wallet_settings() -> OrderWalletSettings:
    return OrderWalletSettings.load()


def _quantize_non_negative(amount: Decimal, *, field: str) -> Decimal:
    if amount < 0:
        raise ValidationError({field: 'Amount must be greater than or equal to zero.'})
    if amount.as_tuple().exponent < -2:
        raise ValidationError({field: 'Amount must have at most 2 decimal places.'})
    return amount.quantize(Decimal('0.01'))


def validate_threshold_ordering(
    *,
    min_wallet_balance_to_order: Decimal,
    low_balance_reminder_threshold: Decimal,
    meal_stop_threshold: Decimal,
) -> None:
    if not (
        min_wallet_balance_to_order
        > low_balance_reminder_threshold
        > meal_stop_threshold
        >= 0
    ):
        raise ValidationError(
            {
                'non_field_errors': [
                    'Thresholds must satisfy: subscription minimum > '
                    'low balance reminder > meal stop ≥ 0.'
                ]
            }
        )


def update_order_wallet_settings(
    *,
    min_wallet_balance_to_order: Decimal | None = None,
    low_balance_reminder_threshold: Decimal | None = None,
    meal_stop_threshold: Decimal | None = None,
) -> OrderWalletSettings:
    settings_obj = OrderWalletSettings.load()
    next_min = (
        min_wallet_balance_to_order
        if min_wallet_balance_to_order is not None
        else settings_obj.min_wallet_balance_to_order
    )
    next_reminder = (
        low_balance_reminder_threshold
        if low_balance_reminder_threshold is not None
        else settings_obj.low_balance_reminder_threshold
    )
    next_stop = (
        meal_stop_threshold
        if meal_stop_threshold is not None
        else settings_obj.meal_stop_threshold
    )

    next_min = _quantize_non_negative(next_min, field='min_wallet_balance_to_order')
    next_reminder = _quantize_non_negative(
        next_reminder, field='low_balance_reminder_threshold'
    )
    next_stop = _quantize_non_negative(next_stop, field='meal_stop_threshold')
    validate_threshold_ordering(
        min_wallet_balance_to_order=next_min,
        low_balance_reminder_threshold=next_reminder,
        meal_stop_threshold=next_stop,
    )

    settings_obj.min_wallet_balance_to_order = next_min
    settings_obj.low_balance_reminder_threshold = next_reminder
    settings_obj.meal_stop_threshold = next_stop
    settings_obj.save()
    return settings_obj


def parse_decimal_amount(value) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Amount must be a valid decimal number.') from exc
    return amount
