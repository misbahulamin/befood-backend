## Context

Support inbox uses Django Channels with `RedisChannelLayer` (`CHANNEL_REDIS_URL` / `REDIS_URL`, default `redis://127.0.0.1:6379/0`). HTTP flows such as admin conversation retrieve call `mark_read_by_admin`, which broadcasts via `broadcast_to_conversation` / `broadcast_admin_inbox`. Those helpers call `async_to_sync(channel_layer.group_send)`. When Redis is down, `group_send` raises `redis.exceptions.ConnectionError` and the entire HTTP request returns 500 — even though the DB mark-read already succeeded (or is about to be rolled back depending on transaction boundaries).

WebSocket connect also requires Redis for `group_add` / receive loops. Tests already override `CHANNEL_LAYERS` to `InMemoryChannelLayer`; local `runserver` does not.

## Goals / Non-Goals

**Goals:**

- HTTP support APIs (retrieve / mark-read / post message) MUST succeed when the channel layer cannot reach Redis.
- Channel broadcast failures MUST be logged and MUST NOT raise out of the service layer.
- Local developers can either run Redis or opt into an InMemory channel layer for single-process local use.
- Document Redis requirement for multi-process / production realtime and the graceful HTTP degradation.

**Non-Goals:**

- Replacing Redis as the production channel backend.
- Building a full offline message queue / retry bus for missed realtime events.
- Making WebSocket fully functional without any channel backend (impossible with Channels groups).
- Changing the public WebSocket or REST payload contracts.

## Decisions

### 1. Soft-fail broadcasts in `support/services/realtime.py`

Wrap `group_send` in both `broadcast_to_conversation` and `broadcast_admin_inbox` with a broad catch for channel/Redis connectivity errors (`OSError`, `ConnectionError`, and Redis client connection errors). Log at `warning` with event type and group name; return without raising.

**Why:** One choke point covers all HTTP callers (mark-read, post message, presence helpers that broadcast). Avoids duplicating try/except in every service.

**Alternatives considered:**

- Catch only in `mark_read_by_admin` — incomplete; send-message and other broadcasts still 500.
- Move broadcast outside the DB transaction and always soft-fail there — good complementary practice, but soft-fail at the broadcast helper is sufficient for the 500.

### 2. Optional local InMemory via env flag

Add something like `CHANNEL_LAYER_BACKEND=redis|inmemory` (or `USE_INMEMORY_CHANNEL_LAYER=true`) honored in `local` / base settings so local runserver can avoid Redis without code edits. Default remains Redis.

**Why:** Matches existing test override pattern; documents an explicit local choice instead of silent fallback that could hide misconfig in staging.

**Alternatives considered:**

- Always InMemory in `local.py` — breaks multi-worker local realtime and surprises anyone expecting Redis.
- Require Redis always — correct for prod, painful for casual local HTTP testing of inbox.

### 3. WebSocket connect: close cleanly on channel-layer failure

In consumers, catch connection errors around `group_add` / initial `group_send` and `close` with a documented server error code (e.g. 1011 or a project-specific 45xx) instead of an unhandled application exception dump when possible.

**Why:** HTTP soft-fail fixes the 500 on retrieve; WebSocket still cannot work without Redis — fail closed with a clear disconnect rather than a noisy traceback loop.

### 4. Tests mock `group_send` failure

Unit/API tests patch channel layer send (or raise from broadcast helpers) and assert admin conversation retrieve still 200 and unread counters updated.

## Risks / Trade-offs

- [Missed realtime events when Redis is down] → Mitigation: log warnings; clients already poll/refetch on open; document that live push needs Redis.
- [InMemory in local hides multi-tab / multi-process bugs] → Mitigation: env opt-in only; docs warn single-process limitation.
- [Swallowing too broad an exception masks real bugs] → Mitigation: catch connection-class errors only; re-raise unexpected exceptions.
- [DB committed mark-read without broadcast] → Mitigation: acceptable degradation; same as Redis outage in prod today after soft-fail.

## Migration Plan

1. Deploy soft-fail broadcast + tests (no env change required).
2. Optionally set local InMemory env for developers without Redis.
3. Production keeps Redis; no rollback beyond reverting the soft-fail wrapper if needed.

## Open Questions

- None blocking; prefer `USE_INMEMORY_CHANNEL_LAYER` boolean for local clarity over a multi-value backend enum unless settings already use a similar pattern.
