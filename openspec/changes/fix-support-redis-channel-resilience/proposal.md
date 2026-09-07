## Why

Opening an admin support conversation detail (`GET /api/v1/web/support/conversations/{id}/`) returns **500** when Redis is not running on `127.0.0.1:6379`. Marking messages read still needs to succeed; realtime broadcast must not take down the HTTP response. Local WebSocket connect also fails for the same missing Redis dependency.

## What Changes

- Make support channel broadcasts **best-effort**: Redis / channel-layer connection failures are logged and swallowed so HTTP mark-read / send-message flows still return success.
- Keep production on Redis channel layer; clarify local-dev options (run Redis, or optional InMemory fallback via env for single-process local run).
- Document that WebSocket realtime still requires a reachable channel backend; without Redis, HTTP works but live push may be degraded or unavailable.
- Add regression tests that simulate channel-layer send failure and assert conversation retrieve / mark-read still returns 200.

## Capabilities

### New Capabilities

- `support-realtime-resilience`: Support inbox HTTP APIs remain available when the Channels Redis backend is unreachable; broadcasts fail soft; local-dev channel-layer guidance is documented.

### Modified Capabilities

- (none — no existing main-spec capability for support inbox; behavior is introduced as a new capability)

## Impact

- `support/services/realtime.py` — wrap `group_send` against connection errors
- Possibly `support/realtime/consumers.py` — safer connect failure handling / clearer close when channel layer is down
- `core/settings/base.py` / `local.py` — optional local InMemory channel layer via env flag
- `support/tests/` — resilience coverage
- `support/docs/backend/support-inbox-ops.md` (and frontend ops note if needed) — Redis requirement + graceful HTTP behavior
