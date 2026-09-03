from rest_framework import serializers

BD_PHONE_COUNTRY_CODE = '880'
BD_PHONE_E164_PREFIX = f'+{BD_PHONE_COUNTRY_CODE}'


def validate_bangladesh_phone(value, field_name='phone'):
    if value in (None, ''):
        return value
    if not value.isdigit() or len(value) != 10:
        raise serializers.ValidationError(
            f'{field_name.replace("_", " ").title()} must be exactly 10 digits and digits only.'
        )
    return value


def format_bd_phone_e164(national):
    """Format a stored BD national phone for API read responses.

    Storage remains 10 digits. Returns ``+880XXXXXXXXXX`` when valid,
    ``None`` when empty, and the stripped raw value for non-conforming data.
    """
    if national is None:
        return None
    value = str(national).strip()
    if not value:
        return None
    if value.startswith(BD_PHONE_E164_PREFIX) and value[1:].isdigit() and len(value) == 14:
        return value
    if value.isdigit() and len(value) == 13 and value.startswith(BD_PHONE_COUNTRY_CODE):
        return f'+{value}'
    if value.isdigit() and len(value) == 10:
        return f'{BD_PHONE_E164_PREFIX}{value}'
    return value


def format_bd_phone_readable(e164_or_national):
    """Human-readable BD phone for print/email (``+880-XXXX-XXXXXX``).

    Normalizes via ``format_bd_phone_e164`` first. Returns ``None`` when empty.
    """
    e164 = format_bd_phone_e164(e164_or_national)
    if e164 is None:
        return None
    if (
        e164.startswith(BD_PHONE_E164_PREFIX)
        and len(e164) == 14
        and e164[1:].isdigit()
    ):
        national = e164[len(BD_PHONE_E164_PREFIX) :]
        return f'{BD_PHONE_E164_PREFIX}-{national[:4]}-{national[4:]}'
    return e164


def normalize_phone_search_term(q: str) -> str:
    """Strip optional ``+880`` / ``880`` so admin ``q`` matches stored national digits."""
    compact = ''.join(str(q).split())
    if compact.startswith(BD_PHONE_E164_PREFIX):
        return compact[len(BD_PHONE_E164_PREFIX) :]
    if (
        compact.startswith(BD_PHONE_COUNTRY_CODE)
        and compact[len(BD_PHONE_COUNTRY_CODE) :].isdigit()
        and len(compact) >= 13
    ):
        return compact[len(BD_PHONE_COUNTRY_CODE) :]
    return compact
