"""Facebook access token verification via Graph API."""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from user_management.models import SocialIdentity
from user_management.services.auth_session import build_customer_auth_response
from user_management.services.social_linking import SocialLinkConflict, resolve_or_create_social_user

logger = logging.getLogger(__name__)


class FacebookOAuthError(Exception):
    def __init__(self, message: str, code: str = 'FACEBOOK_OAUTH_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def _graph_version() -> str:
    return getattr(settings, 'FACEBOOK_GRAPH_VERSION', 'v21.0') or 'v21.0'


def verify_facebook_access_token(access_token: str) -> dict:
    """
    Validate a Facebook user access token and fetch profile fields.

    Uses app credentials for debug_token + /me profile fetch.
    """
    token = (access_token or '').strip()
    if not token:
        raise FacebookOAuthError('Facebook access token is required.', code='TOKEN_REQUIRED')

    app_id = getattr(settings, 'FACEBOOK_APP_ID', '') or ''
    app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '') or ''
    if not app_id or not app_secret:
        raise FacebookOAuthError(
            'Facebook OAuth is not configured.',
            code='FACEBOOK_NOT_CONFIGURED',
        )

    version = _graph_version()
    app_token = f'{app_id}|{app_secret}'
    debug_url = f'https://graph.facebook.com/{version}/debug_token'
    try:
        debug_resp = requests.get(
            debug_url,
            params={'input_token': token, 'access_token': app_token},
            timeout=30,
        )
        debug_resp.raise_for_status()
        debug_data = debug_resp.json().get('data') or {}
    except requests.RequestException as exc:
        logger.warning('Facebook debug_token failed: %s', type(exc).__name__)
        raise FacebookOAuthError('Unable to verify Facebook token.') from exc

    if not debug_data.get('is_valid'):
        raise FacebookOAuthError('Invalid Facebook access token.', code='INVALID_TOKEN')

    if str(debug_data.get('app_id') or '') != str(app_id):
        raise FacebookOAuthError('Invalid Facebook access token.', code='INVALID_APP')

    me_url = f'https://graph.facebook.com/{version}/me'
    try:
        me_resp = requests.get(
            me_url,
            params={
                'fields': 'id,email,first_name,last_name,name',
                'access_token': token,
            },
            timeout=30,
        )
        me_resp.raise_for_status()
        profile = me_resp.json()
    except requests.RequestException as exc:
        logger.warning('Facebook /me failed: %s', type(exc).__name__)
        raise FacebookOAuthError('Unable to fetch Facebook profile.') from exc

    if not profile.get('id'):
        raise FacebookOAuthError('Invalid Facebook profile.', code='INVALID_PROFILE')

    # Email presence is not email ownership. Facebook Graph does not assert
    # email_verified the way Google ID tokens do; keep provider identity separate.
    profile['email_verified'] = False
    return profile


def login_with_facebook(
    access_token: str,
    *,
    device_token: str | None = None,
    platform: str | None = None,
    user_agent: str = '',
) -> dict:
    profile = verify_facebook_access_token(access_token)
    try:
        user, _identity, _created = resolve_or_create_social_user(
            provider=SocialIdentity.Provider.FACEBOOK,
            provider_user_id=str(profile['id']),
            email=profile.get('email') or '',
            email_verified=False,
            first_name=profile.get('first_name') or '',
            last_name=profile.get('last_name') or '',
        )
    except SocialLinkConflict as exc:
        raise FacebookOAuthError(exc.message, code='SOCIAL_CONFLICT') from exc

    return build_customer_auth_response(
        user,
        auth_provider='facebook',
        device_token=device_token,
        platform=platform,
        user_agent=user_agent,
    )
