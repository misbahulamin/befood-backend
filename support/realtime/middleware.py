"""DRF Token authentication for Channels WebSocket connections."""

from __future__ import annotations

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token


@database_sync_to_async
def _user_from_token(token_key: str):
    if not token_key:
        return AnonymousUser()
    try:
        token = Token.objects.select_related('user').get(key=token_key)
    except Token.DoesNotExist:
        return AnonymousUser()
    user = token.user
    if not user.is_active:
        return AnonymousUser()
    return user


def _extract_token(scope) -> str:
    query_string = scope.get('query_string', b'').decode()
    for part in query_string.split('&'):
        if not part:
            continue
        key, _, value = part.partition('=')
        if key == 'token' and value:
            return value

    headers = dict(scope.get('headers') or [])
    auth = headers.get(b'authorization', b'').decode()
    if auth.lower().startswith('token '):
        return auth.split(' ', 1)[1].strip()
    return ''


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        token_key = _extract_token(scope)
        scope['user'] = await _user_from_token(token_key)
        return await super().__call__(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    return TokenAuthMiddleware(inner)
