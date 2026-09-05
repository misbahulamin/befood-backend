"""Centralized email/phone normalization for customer identity."""

from __future__ import annotations

import re

from rest_framework import serializers

from user_management.validators import BD_PHONE_COUNTRY_CODE, BD_PHONE_E164_PREFIX

_NON_DIGIT_RE = re.compile(r'\D+')


class PhoneNormalizationError(serializers.ValidationError):
    """Raised when a phone cannot be normalized to a valid BD mobile."""

    def __init__(self, message: str = 'Enter a valid Bangladesh mobile number.'):
        super().__init__(message)


def normalize_email(raw: str | None) -> str:
    """Normalize email for storage, uniqueness, and linking comparisons."""
    return (raw or '').strip().lower()


def normalize_phone_number(raw: str | None) -> str:
    """
    Normalize BD mobile inputs to canonical 10-digit national storage form.

    Accepted examples (all → ``1712345678``):
    - ``01712345678``
    - ``+8801712345678``
    - ``8801712345678``
    - spaced/dashed variants of the above

    Storage matches existing ``CustomerProfile.phone`` (max 10 digits, no leading 0).
    """
    if raw is None:
        raise PhoneNormalizationError()

    compact = _NON_DIGIT_RE.sub('', str(raw).strip())
    if not compact:
        raise PhoneNormalizationError()

    if compact.startswith(BD_PHONE_COUNTRY_CODE) and len(compact) >= 13:
        compact = compact[len(BD_PHONE_COUNTRY_CODE) :]
    elif compact.startswith('0') and len(compact) == 11:
        compact = compact[1:]

    if not compact.isdigit() or len(compact) != 10:
        raise PhoneNormalizationError()

    # BD mobiles: national significant number starts with 1 (13/14/15/16/17/18/19…).
    if not compact.startswith('1'):
        raise PhoneNormalizationError()

    return compact


def phone_to_sms_dial(canonical: str) -> str:
    """Convert canonical 10-digit storage form to SMS.NET.BD dial string (880…)."""
    national = normalize_phone_number(canonical)
    return f'{BD_PHONE_COUNTRY_CODE}{national}'


def phone_to_e164(canonical: str) -> str:
    """Convert canonical storage form to E.164 (+880…)."""
    national = normalize_phone_number(canonical)
    return f'{BD_PHONE_E164_PREFIX}{national}'
