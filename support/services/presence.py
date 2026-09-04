"""Ephemeral presence keys for support chat (Redis preferred; memory fallback)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

PRESENCE_CUSTOMER_PREFIX = 'support:presence:customer:'
PRESENCE_ADMIN_PREFIX = 'support:presence:admin:'
PRESENCE_AGENTS_KEY = 'support:presence:agents'
PRESENCE_CONVERSATION_ADMINS_PREFIX = 'support:presence:conversation_admins:'


def _ttl() -> int:
    return int(getattr(settings, 'SUPPORT_PRESENCE_TTL_SECONDS', 60) or 60)


def mark_customer_online(*, user_id: int, conversation_public_id: str) -> None:
    cache.set(f'{PRESENCE_CUSTOMER_PREFIX}{user_id}', conversation_public_id, timeout=_ttl())
    cache.set(
        f'{PRESENCE_CUSTOMER_PREFIX}conv:{conversation_public_id}',
        user_id,
        timeout=_ttl(),
    )


def mark_customer_offline(*, user_id: int, conversation_public_id: str) -> None:
    cache.delete(f'{PRESENCE_CUSTOMER_PREFIX}{user_id}')
    cache.delete(f'{PRESENCE_CUSTOMER_PREFIX}conv:{conversation_public_id}')


def mark_admin_online(*, user_id: int, conversation_public_id: str | None = None) -> None:
    cache.set(f'{PRESENCE_ADMIN_PREFIX}{user_id}', '1', timeout=_ttl())
    agents = set(cache.get(PRESENCE_AGENTS_KEY) or [])
    agents.add(user_id)
    cache.set(PRESENCE_AGENTS_KEY, list(agents), timeout=_ttl())
    if conversation_public_id:
        key = f'{PRESENCE_CONVERSATION_ADMINS_PREFIX}{conversation_public_id}'
        admins = set(cache.get(key) or [])
        admins.add(user_id)
        cache.set(key, list(admins), timeout=_ttl())


def mark_admin_offline(*, user_id: int, conversation_public_id: str | None = None) -> None:
    cache.delete(f'{PRESENCE_ADMIN_PREFIX}{user_id}')
    agents = set(cache.get(PRESENCE_AGENTS_KEY) or [])
    agents.discard(user_id)
    if agents:
        cache.set(PRESENCE_AGENTS_KEY, list(agents), timeout=_ttl())
    else:
        cache.delete(PRESENCE_AGENTS_KEY)
    if conversation_public_id:
        key = f'{PRESENCE_CONVERSATION_ADMINS_PREFIX}{conversation_public_id}'
        admins = set(cache.get(key) or [])
        admins.discard(user_id)
        if admins:
            cache.set(key, list(admins), timeout=_ttl())
        else:
            cache.delete(key)


def refresh_presence(*, user_id: int, is_admin: bool, conversation_public_id: str | None) -> None:
    if is_admin:
        mark_admin_online(user_id=user_id, conversation_public_id=conversation_public_id)
    elif conversation_public_id:
        mark_customer_online(user_id=user_id, conversation_public_id=conversation_public_id)


def is_customer_present(conversation_public_id: str) -> bool:
    return cache.get(f'{PRESENCE_CUSTOMER_PREFIX}conv:{conversation_public_id}') is not None


def is_any_admin_present() -> bool:
    agents = cache.get(PRESENCE_AGENTS_KEY) or []
    return bool(agents)


def is_admin_present_on_conversation(conversation_public_id: str) -> bool:
    admins = cache.get(f'{PRESENCE_CONVERSATION_ADMINS_PREFIX}{conversation_public_id}') or []
    return bool(admins) or is_any_admin_present()


def customer_online_for_conversation(conversation_public_id: str) -> bool:
    return is_customer_present(conversation_public_id)


def support_agent_online() -> bool:
    return is_any_admin_present()
