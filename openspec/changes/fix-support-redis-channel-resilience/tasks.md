## 1. Soft-fail broadcasts

- [ ] 1.1 In `support/services/realtime.py`, wrap `group_send` in `broadcast_to_conversation` and `broadcast_admin_inbox` to catch Redis/network connection errors, log a warning with event context, and return without raising
- [ ] 1.2 Optionally harden WebSocket `connect` in `support/realtime/consumers.py` so channel-layer connection failures close cleanly instead of unhandled application exceptions

## 2. Local channel-layer opt-in

- [ ] 2.1 Add env-gated InMemory channel layer option for local/dev settings (default remains Redis)
- [ ] 2.2 Document Redis vs InMemory in `support/docs/backend/support-inbox-ops.md` (and note HTTP soft-fail when Redis is down)

## 3. Tests and verification

- [ ] 3.1 Add/extend support tests that simulate channel `group_send` connection failure and assert admin conversation retrieve still returns 200 with mark-read applied
- [ ] 3.2 Add/extend coverage that message post HTTP succeeds when broadcast fails soft
- [ ] 3.3 Run the relevant support test module(s) and confirm they pass
