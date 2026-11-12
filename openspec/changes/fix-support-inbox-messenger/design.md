# Design

## Context

See proposal.md — Why. Observed production failure mode: PostgreSQL `ORDER BY last_message_at DESC` puts NULLs first; empty `SupportConversation` rows (created on support open via `get_or_create`) occupy early pages. Admin inbox fan-out already exists (`ADMIN_INBOX_GROUP` + `broadcast_admin_inbox`), but only `SupportConversationConsumer` joins that group when a conversation is open. Frontend `compareByRecency` treats null as `0` (empties sink), disagreeing with server order. List uses page-number pagination (`page_size` 20) plus ~45s refetch.

This OpenSpec root is `befood-backend`. Frontend work targets sibling `befood-frontend` and is specified/planned here but applied outside this repo’s edit root.

## Goals / Non-Goals

**Goals:**

- Deterministic admin list order: newest real activity first; empties last or hidden by default.
- Inbox-wide live updates without requiring an open conversation socket.
- Additive list/WS fields for Messenger preview (`last_message_sender`, avatar on summary).
- Client cache strategy that move-to-tops across infinite pages with scroll UX and unread chrome.
- Tests covering ordering, empty filter, sender field, inbox consumer ACL/events, and client sorter parity.

**Non-Goals:**

- Changing customer support REST/WS message contracts beyond shared broadcast side effects.
- Replacing Redis channel layer or rewriting presence/typing protocols.
- Backfilling historical empty conversations or deleting them.
- Cursor/keyset pagination on the API (keep page-number pages; client uses infinite query over `page`).
- Changing unread accounting rules beyond consuming existing counters in UI/title.

## Decisions

### 1. NULLS LAST ordering via Django expression + index migration

Use `order_by(F('last_message_at').desc(nulls_last=True), '-id')` in `apply_admin_conversation_filters` and align `SupportConversation.Meta.ordering`. Replace the composite index on `(-last_message_at, -id)` with an expression index matching NULLS LAST (PostgreSQL). SQLite test DB: verify ordering still places nulls after non-nulls (Django/SQLite nulls-last support for the expression); if a test dialect gap appears, assert via service-level expected order helpers rather than relying on PG-only index semantics.

**Alternatives considered:** Coalesce nulls to epoch in ORDER BY (distorts “never messaged”); filter-only without NULLS LAST (insufficient when `include_empty=true`).

### 2. Default exclude empties; allowlist `include_empty`

Extend `apply_admin_conversation_filters` with `include_empty: bool = False`. When false, `filter(last_message_at__isnull=False)` before ordering (applies to search too). Add `include_empty` to `AdminSupportConversationViewSet` allowed query params and OpenAPI. Truthy parsing mirrors `has_unread`.

**Alternatives considered:** Soft-delete empties on create (behavior change for “open support” UX); hide only in UI (server still pages empties).

### 3. Denormalized `last_message_sender` on `SupportConversation`

Add nullable CharField with choices aligned to message sender types used for last message (`customer` | `admin`; null when no messages). Set it in `post_message` alongside `last_message` / `last_message_at`. Expose on `AdminConversationListSerializer` and in `serialize_conversation_summary`. Include `profile_picture_url` under nested `customer` in the summary using the existing profile-picture helper (no request in WS path → absolute/public URL rules as today for list serializer when request absent).

**Alternatives considered:** Annotate latest message per list query (N+1 or heavy subquery); derive only in serializer from related messages (list cost).

### 4. Dedicated `SupportAdminInboxConsumer` at `ws/support/inbox/`

New consumer: auth required; `is_verified_admin` or close `4403`; `group_add(ADMIN_INBOX_GROUP)`; forward `support.event` payloads already used by conversation consumer. Do not join a conversation group. Keep conversation consumer’s join to `ADMIN_INBOX_GROUP` for admins in an open chat (harmless double membership / same channel). Verify `_broadcast_message` and mark-read paths already call `broadcast_admin_inbox('conversation.updated', ...)`.

**Alternatives considered:** Always-on admin presence channel mixed with presence semantics; SSE poll replacement (worse multi-worker fan-out fit).

### 5. Frontend: infinite query + inbox WS + move-to-top

In `befood-frontend`: switch list to TanStack `useInfiniteQuery` keyed by filters (not `page` in URL). New `useAdminSupportInboxRealtime` always mounted on the page; on `conversation.updated`, strip id from all pages and prepend to page 0; skip unread bump when `c` matches open conversation. Decouple list refetch interval from per-conversation `realtimeConnected`; poll only when inbox socket down. Align `compareByRecency` with nulls-last + id/`public_id` DESC. Messenger list chrome as specified in client spec.

**Alternatives considered:** Keep Prev/Next and only fix sort (fails instant top-of-inbox UX); rely solely on 20s poll (misses ≤1s acceptance).

### 6. Cross-repo apply sequencing

Implement and test backend contract first (ordering, filter, fields, inbox WS). Then frontend against that contract. OpenSpec apply in this root covers backend + docs/tests here; frontend tasks are explicit sibling-repo steps.

## Risks / Trade-offs

- [Default list shrinks] → Document `include_empty`; ops/admin tools that expected empties must opt in.
- [Expression index PG vs SQLite tests] → Assert behavioral order in API tests; migration uses Django `Index`/`F` expressions compatible with project PG production.
- [Double admin membership in ADMIN_INBOX_GROUP] → Acceptable; events delivered once per connection channel.
- [Infinite cache move-to-top duplicates/count drift] → Normalize by public_id across pages; adjust `count` carefully when inserting unseen threads.
- [Notification sound / localStorage] → try/catch; mute default or respect stored preference; never block render.
- [Frontend outside apply edit root] → Track sibling PR; acceptance requires both repos.

## Migration Plan

1. Ship backend migration (field + index) and deploy ASGI routes for `ws/support/inbox/`.
2. Deploy backend before or with frontend that sends `include_empty` / consumes `last_message_sender` (additive fields safe for old clients; new client expects empties hidden).
3. Rollback: revert deploy; migration reverse drops field/index; old clients ignore unknown fields. Empty-exclusion behavior reverts with code rollback.

## Open Questions

None material for specs/tasks; mute-toggle default (muted vs unmuted) left to frontend implementer with a sensible quiet default if product does not specify.
