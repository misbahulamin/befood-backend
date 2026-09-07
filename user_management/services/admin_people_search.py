"""Shared free-text people-search Q builder for admin lists.

Keeps admin list search consistent across the customer directory, support
inbox, subscription board, and wallet funding review: same phone
normalization, same UUID handling, same field coverage.
"""

from __future__ import annotations

import re
import uuid

from django.db.models import Q

from user_management.validators import normalize_phone_search_term

_PEOPLE_NAME_FIELDS = ('user__first_name', 'user__last_name', 'user__username')
_CANONICAL_UUID_LENGTH = 36
_WHITESPACE_RE = re.compile(r'\s+')


def looks_like_uuid(term: str) -> bool:
    """True only for canonical ``xxxxxxxx-xxxx-...`` UUIDs.

    Short hex-ish terms (phones, numeric ids) parse via ``uuid.UUID`` with
    zero padding, so they must not be treated as UUID lookups.
    """
    term = str(term or '').strip()
    if len(term) != _CANONICAL_UUID_LENGTH:
        return False
    try:
        uuid.UUID(term)
    except ValueError:
        return False
    return True


def build_customer_people_q(q: str, *, customer_prefix: str = '') -> Q:
    """Q matching a customer person across identity fields.

    Rooted on ``CustomerProfile``; pass ``customer_prefix`` (e.g.
    ``customer__``) when the queryset root is a related model. Matches user
    email, first/last name, username, phone (optional ``+880`` / ``880``
    stripped like the customer directory), multi-word name pairs, and the
    customer ``public_id`` exactly when ``q`` parses as a UUID.
    """
    term = _WHITESPACE_RE.sub(' ', (q or '').strip())
    if not term:
        return Q()

    conditions = Q(**{f'{customer_prefix}user__email__icontains': term})
    for field in _PEOPLE_NAME_FIELDS:
        conditions |= Q(**{f'{customer_prefix}{field}__icontains': term})

    # "Md Rahim" / "MD  Rahim" → match first+last without requiring exact concat column.
    parts = [part for part in term.split(' ') if part]
    if len(parts) >= 2:
        conditions |= Q(
            **{
                f'{customer_prefix}user__first_name__icontains': parts[0],
                f'{customer_prefix}user__last_name__icontains': parts[-1],
            }
        )

    phone_term = normalize_phone_search_term(term)
    if phone_term and any(char.isdigit() for char in phone_term):
        conditions |= Q(**{f'{customer_prefix}phone__icontains': phone_term})

    if looks_like_uuid(term):
        conditions |= Q(**{f'{customer_prefix}public_id': term})

    return conditions


def build_subscription_people_q(q: str) -> Q:
    """Customer people-search plus the subscription's own ``public_id``."""
    term = _WHITESPACE_RE.sub(' ', (q or '').strip())
    conditions = build_customer_people_q(term, customer_prefix='customer__')
    if looks_like_uuid(term):
        conditions |= Q(public_id=term)
    return conditions
