"""Token-header authentication with per-session AuthSession support."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication

from user_management.models import AuthSession


class AuthSessionAuthentication(TokenAuthentication):
    """
    Authenticate ``Authorization: Token <key>`` against AuthSession first.

    Falls back to the legacy DRF ``authtoken.Token`` model so admin/deliveryman
    and any unmigrated tokens keep working.
    """

    keyword = 'Token'

    def authenticate_credentials(self, key):
        try:
            session = AuthSession.objects.select_related('user').get(
                key=key,
                revoked_at__isnull=True,
            )
        except AuthSession.DoesNotExist:
            return super().authenticate_credentials(key)

        if not session.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')

        AuthSession.objects.filter(pk=session.pk).update(last_used_at=timezone.now())
        return (session.user, session)
