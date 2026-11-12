# Proposal

## Why

Admin Support Inbox on production shows new customer messages in the middle of the list (often page 7+) because PostgreSQL `ORDER BY last_message_at DESC` places NULL first, and empty conversations (`last_message_at IS NULL`) outnumber real threads. Admins also only receive inbox WebSocket updates when a conversation is open, so the list depends on slow polling and cannot reliably jump a conversation to the top across page-based pagination. The product goal is Messenger-like ordering and live list updates.

## What Changes

- Fix admin conversation ordering to `last_message_at DESC NULLS LAST`, then `-id`, including model `Meta.ordering` and a matching index migration.
- Hide empty conversations from the default admin list/search; allow opt-in via `include_empty=true` (allowlisted query param).
- Add `last_message_sender` (`customer` | `admin` | null) on the admin list serializer and WS conversation summary; prefer a denormalized field on `SupportConversation` updated with last-message writes (avoid N+1). Include `customer.profile_picture_url` in the WS summary when missing.
- Add admin-only inbox WebSocket `ws/support/inbox/` that joins `ADMIN_INBOX_GROUP` without requiring an open conversation; keep the per-conversation consumer unchanged. Verify every customer/admin message path still broadcasts `conversation.updated` to the admin inbox group.
- Frontend (sibling `befood-frontend`): Messenger-style inbox list UX, ordering parity with server, infinite scroll, page-level inbox realtime hook with move-to-top cache updates, unread tab title, optional notification sound, and polling only while the inbox socket is disconnected.
- Backend + frontend tests for ordering, empty filtering, `last_message_sender`, inbox consumer ACL/events, and client sorter parity.

## Capabilities

### New Capabilities

- `admin-support-inbox-client`: Admin Support Inbox web client behavior — Messenger-like list presentation, infinite scroll, inbox-scoped realtime, unread tab title, and client/server ordering parity.

### Modified Capabilities

- `admin-support-inbox`: Default list excludes empty conversations; `include_empty` filter; NULLS LAST ordering; list payload includes `last_message_sender`.
- `support-realtime-messaging`: Dedicated verified-admin inbox WebSocket at `ws/support/inbox/`; conversation summary payload gains `last_message_sender` and customer profile picture URL for inbox fan-out.

## Impact

- Backend (`befood-backend`): `support/models.py`, migrations, `support/services/conversations.py`, `support/services/messages.py`, `support/services/realtime.py`, `support/api/serializers.py`, `support/api/admin_views.py`, `support/realtime/consumers.py`, `support/realtime/routing.py`, OpenAPI/docs under `support/docs/`, `support/tests/`.
- Frontend (`befood-frontend`, sibling repo — out of this OpenSpec root’s apply edit scope): admin support inbox page, list/filters components, hooks, mappers/types, vitest.
- API additive fields / optional query param (backward compatible for clients that ignore unknown response fields). Default list result set shrinks by excluding empties (**behavior change** for callers that previously received empty threads without `include_empty`).
- No change to customer support chat REST/WS contracts beyond existing shared broadcast side effects.
