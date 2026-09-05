"""Google ID token verification for customer OAuth login."""

from __future__ import annotations

from django.conf import settings

from user_management.models import SocialIdentity
from user_management.services.auth_session import build_customer_auth_response
from user_management.services.social_linking import SocialLinkConflict, resolve_or_create_social_user


class GoogleOAuthError(Exception):
    def __init__(self, message: str, code: str = 'GOOGLE_OAUTH_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def _audience_client_ids() -> list[str]:
    ids = []
    web = getattr(settings, 'GOOGLE_WEB_CLIENT_ID', '') or ''
    android = getattr(settings, 'GOOGLE_ANDROID_CLIENT_ID', '') or ''
    if web:
        ids.append(web)
    if android:
        ids.append(android)
    return ids


def verify_google_id_token(id_token: str) -> dict:
    """
    Verify a Google ID token and return claims.

    Requires ``GOOGLE_WEB_CLIENT_ID`` and/or ``GOOGLE_ANDROID_CLIENT_ID``.
    """
    token = (id_token or '').strip()
    if not token:
        raise GoogleOAuthError('Google ID token is required.', code='TOKEN_REQUIRED')

    audiences = _audience_client_ids()
    if not audiences:
        raise GoogleOAuthError(
            'Google OAuth is not configured.',
            code='GOOGLE_NOT_CONFIGURED',
        )

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except ImportError as exc:
        raise GoogleOAuthError(
            'Google auth libraries are unavailable.',
            code='GOOGLE_LIBRARY_MISSING',
        ) from exc

    request = google_requests.Request()
    claims = None
    last_error = None
    for audience in audiences:
        try:
            claims = google_id_token.verify_oauth2_token(token, request, audience=audience)
            break
        except ValueError as exc:
            last_error = exc

    if claims is None:
        raise GoogleOAuthError('Invalid Google ID token.', code='INVALID_TOKEN') from last_error

    if not claims.get('sub'):
        raise GoogleOAuthError('Invalid Google ID token.', code='INVALID_TOKEN')

    return claims


def login_with_google(
    id_token: str,
    *,
    device_token: str | None = None,
    platform: str | None = None,
    user_agent: str = '',
) -> dict:
    claims = verify_google_id_token(id_token)
    email = claims.get('email') or ''
    email_verified = bool(claims.get('email_verified'))
    try:
        user, _identity, _created = resolve_or_create_social_user(
            provider=SocialIdentity.Provider.GOOGLE,
            provider_user_id=str(claims['sub']),
            email=email,
            email_verified=email_verified,
            first_name=claims.get('given_name') or '',
            last_name=claims.get('family_name') or '',
        )
    except SocialLinkConflict as exc:
        raise GoogleOAuthError(exc.message, code='SOCIAL_CONFLICT') from exc

    return build_customer_auth_response(
        user,
        auth_provider='google',
        device_token=device_token,
        platform=platform,
        user_agent=user_agent,
    )
