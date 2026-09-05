"""SMS.NET.BD HTTP client for phone OTP delivery."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from user_management.services.identity_normalization import phone_to_sms_dial

logger = logging.getLogger(__name__)


class SmsNetBdError(Exception):
    """Raised when SMS.NET.BD send fails or credentials are missing."""

    def __init__(self, message: str, code: str = 'SMS_PROVIDER_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def _require_credentials() -> tuple[str, str]:
    api_key = getattr(settings, 'SMS_NET_BD_API_KEY', '') or ''
    send_url = getattr(settings, 'SMS_NET_BD_SEND_SMS_URL', '') or ''
    if not api_key or not send_url:
        raise SmsNetBdError(
            'SMS provider is not configured.',
            code='SMS_NOT_CONFIGURED',
        )
    return api_key, send_url


def send_sms(canonical_phone: str, message: str) -> dict:
    """
    Send SMS via SMS.NET.BD.

    Converts canonical 10-digit storage form to provider dial format in this
    adapter only; domain code keeps phones canonical.
    """
    api_key, send_url = _require_credentials()
    dial = phone_to_sms_dial(canonical_phone)
    payload = {
        'api_key': api_key,
        'msg': message,
        'to': dial,
    }
    try:
        response = requests.post(send_url, data=payload, timeout=30)
    except requests.RequestException as exc:
        logger.warning('SMS.NET.BD request failed: %s', type(exc).__name__)
        raise SmsNetBdError('Unable to send SMS. Please try again later.') from exc

    try:
        body = response.json()
    except ValueError:
        body = {'raw': response.text}

    # SMS.NET.BD typically returns error: 0 on success.
    error_code = body.get('error') if isinstance(body, dict) else None
    if response.status_code >= 400 or (error_code not in (0, '0', None) and error_code != 0):
        if error_code in (0, '0'):
            return body if isinstance(body, dict) else {'result': body}
        logger.warning(
            'SMS.NET.BD send failed status=%s error=%s',
            response.status_code,
            error_code,
        )
        raise SmsNetBdError('Unable to send SMS. Please try again later.')

    return body if isinstance(body, dict) else {'result': body}


def send_otp_sms(canonical_phone: str, otp_code: str) -> dict:
    message = f'Your BeFood verification code is {otp_code}. Do not share this code.'
    return send_sms(canonical_phone, message)
