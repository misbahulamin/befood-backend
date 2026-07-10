from rest_framework import serializers


def validate_bangladesh_phone(value, field_name='phone'):
    if value in (None, ''):
        return value
    if not value.isdigit() or len(value) != 10:
        raise serializers.ValidationError(
            f'{field_name.replace("_", " ").title()} must be exactly 10 digits and digits only.'
        )
    return value
