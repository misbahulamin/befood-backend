"""Referral program settings (live commission percent)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from referrals.models import ReferralProgramSettings


def get_referral_program_settings() -> ReferralProgramSettings:
    return ReferralProgramSettings.load()


def _quantize_commission_percent(value: Decimal) -> Decimal:
    if value < 0 or value > 100:
        raise ValidationError(
            {
                'referral_commission_percent': [
                    'Commission percent must be between 0 and 100 inclusive.'
                ]
            }
        )
    if value.as_tuple().exponent < -2:
        raise ValidationError(
            {
                'referral_commission_percent': [
                    'Commission percent must have at most 2 decimal places.'
                ]
            }
        )
    return value.quantize(Decimal('0.01'))


def parse_commission_percent(value) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            {
                'referral_commission_percent': [
                    'Commission percent must be a valid decimal number.'
                ]
            }
        ) from exc
    return _quantize_commission_percent(amount)


def update_referral_commission_percent(
    *,
    referral_commission_percent: Decimal,
) -> ReferralProgramSettings:
    settings_obj = ReferralProgramSettings.load()
    settings_obj.commission_percent = parse_commission_percent(
        referral_commission_percent
    )
    settings_obj.full_clean()
    settings_obj.save(update_fields=['commission_percent', 'updated_at'])
    return settings_obj
