## Context

Prior plan scoped a **poll-only** support inbox (explicitly no WebSockets). Product scope is now a **live support chat**: REST for bootstrap/history + Django Channels for real-time messages, typing, and presence, with FCM when the peer is offline.

**Current backend facts:**

| Area | State |
|------|--------|
| User | Django `auth.User` + `CustomerProfile` / `AdminProfile` |
| API auth | DRF `TokenAuthentication` (`Authorization: Token …`) |
| Admin APIs | `/api/v1/web/...` + `IsVerifiedAdmin` (no `/api/v1/admin/`) |
| Notifications | `create_inbox_notification`, `get_user_device_tokens`, `send_to_tokens` |
| ASGI | `core.asgi` = bare `get_asgi_application()` only |
| Channels | **Not installed** (`channels` / `channels-redis` / `daphne` absent from requirements) |
| Redis Python pkg | Present (`redis` in `requirements.txt`); no `CHANNEL_LAYERS` / Celery Redis settings found in `core/settings` |
| Production | Gunicorn via supervisor + nginx (HTTP/WSGI); WebSocket path not established |

Stakeholders: mobile customers, admin web SPA, ops/deploy (Redis + ASGI).

## Goals / Non-Goals

**Goals:**

- One permanent conversation per customer; immutable messages with dual read flags and unread counters.
- REST for initial load, pagination, fallback send, admin list/ops.
- Authenticated WebSocket for instant `message`, `typing`, `presence`, `message.read`.
- Typing/presence ephemeral (Redis/channel layer), not durable DB rows.
- Offline peer → existing FCM/inbox (customer) and existing admin email/ops pattern; online peer → WS only (avoid duplicate push spam when connected).
- Indexes + pagination for history growth; BOLA on REST and WS.

**Non-Goals:**

- Voice, video, attachments/images, multi-agent assignment, canned replies, C2C chat.
- Guaranteed delivery queues beyond best-effort FCM/email logging (v1).
- Storing typing/presence permanently in PostgreSQL.

## Decisions

### 1. App & persistence (unchanged core model, expanded realtime)

**Choice:** Django app `support` with:

**`SupportConversation`:** `public_id` (PublicIdMixin), OneToOne `CustomerProfile`, `status` ∈ open|closed|archived, `last_message` preview, `last_message_at`, `customer_unread_count`, `admin_unread_count`, timestamps.

**`SupportMessage`:** `public_id`, FK conversation, `sender_type` ∈ customer|admin|system, `sender_user` (nullable for system), `body`, `is_read_by_customer`, `is_read_by_admin`, `created_at`. No update/delete client APIs.

**Why:** Matches product schema; `CustomerProfile` holds phone; public UUID avoids leaking sequential IDs on WS paths.

### 2. Dual transport: REST + WebSocket

**Choice:**

- REST = source of truth load + admin list + fallback when WS unavailable.
- WS = live fan-out after the same service-layer persist used by REST (single write path).

Flow: validate → `services` persist message + update conversation → `channel_layer.group_send` → optional offline notify on_commit.

**Why:** Avoids divergent message logic; REST remains usable for clients that cannot hold a socket.

### 3. Introduce Django Channels + Redis channel layer

**Choice:**

- Dependencies: `channels`, `channels-redis`, `daphne` (and/or run under uvicorn).
- `CHANNEL_LAYERS` Redis config from env (e.g. `REDIS_URL` / `CHANNEL_REDIS_URL`).
- Local/dev: Redis required for multi-process; InMemory channel layer **only** for isolated unit tests if needed—not for staging/prod.
- `core/asgi.py`: `ProtocolTypeRouter` with `http` → Django ASGI, `websocket` → AuthMiddlewareStack + URLRouter.

**Why:** Preferred stack for Django; Redis already a common Celery companion and listed in requirements.

**Alternatives:** Long-polling only — rejected by product. Socket.IO sidecar — rejected (second stack).

### 4. WebSocket URL & events

**Choice:** Canonical path:

```text
ws[s]://<host>/ws/support/<conversation_public_id>/
```

Use **conversation `public_id`**, never integer PK.

Client → server (examples):

| Event | Purpose |
|-------|---------|
| `message.send` | `{ body }` → persist + broadcast `message.receive` |
| `typing.start` / `typing.stop` | Ephemeral; no DB write |
| `presence.ping` or connect/disconnect | Drive online/offline |
| `message.read` | Mark peer messages read; update unread counters; broadcast |

Server → client:

| Event | Purpose |
|-------|---------|
| `message.receive` | New message payload |
| `typing.start` / `typing.stop` | Show/hide indicator |
| `presence.online` / `presence.offline` | Peer/support presence |
| `message.read` | Read-state sync |
| `error` | Auth/validation failures |

Envelope: JSON `{ "type": "<event>", "payload": { ... } }` (document exact keys in frontend docs).

**Admin inbox list live updates:** Admins also subscribe to a **staff group** (e.g. `support.admin.inbox`) to receive conversation list bumps (last message, unread) without opening each thread—optional but recommended for left-pane UX.

### 5. WebSocket authentication & authorization

**Choice:**

- Require auth on connect (reject anonymous).
- Accept DRF Token via query `?token=` and/or first-message auth if needed; prefer `Authorization` subprotocol/header where clients allow—document mobile/web practical choice (`token` query is common for browsers).
- After auth: customer may join **only** their conversation; verified admin may join any conversation + admin inbox group.
- Close with policy violation if conversation_id does not match ACL (do not leak existence beyond `4403`/`4404` style close codes—document).

**Why:** Matches existing Token model; BOLA critical on WS.

### 6. Typing indicators

**Choice:** On `typing.start`/`typing.stop`, `group_send` to conversation group excluding sender. TTL/auto-stop: if no stop within N seconds (e.g. 5s), consumers/clients clear locally; server may ignore persistence entirely.

**Why:** Product forbids DB persistence for typing.

### 7. Presence (online/offline)

**Choice:** Redis keys keyed by user id + role (e.g. `support:presence:user:{id}`) with short TTL refreshed by ping/connect; conversation peers see:

- Admin UI: customer online for that thread (and optionally global).
- Customer UI: “Support agent online” if **any** verified admin is present on that conversation group or a global `support.agents` presence set.

On disconnect: remove presence, broadcast `presence.offline`. Prefer **not** storing online flags on `SupportConversation`.

**Why:** Matches “prefer cache, not permanent DB.”

### 8. Offline notifications (reuse FCM/email)

**Choice:**

- After message persist, if **recipient side has no active WS presence** (Redis check):
  - Admin → customer: `create_inbox_notification` + FCM (`notification_type`/`screen` support).
  - Customer → admin: email verified admins (funding-style recipient list) and/or future admin push if already trivial—**no new push platform**.
- If recipient is online on the conversation (or admin inbox socket for admins): skip FCM/email to reduce noise (still persist message).

**Why:** Product rule: notify when offline; reuse existing stack.

### 9. Unread & read

**Choice:** Same counters as before; `message.read` (WS) and opening REST detail/inbox clear the appropriate side and broadcast so both UIs sync badges.

### 10. Deploy / nginx / process model

**Choice:**

1. Provision Redis reachable by app (document URL env var).
2. Run ASGI app with Daphne or Uvicorn workers for at least `/ws/` (options: full cutover HTTP+WS to Daphne/Uvicorn, or split: Gunicorn for REST + Daphne for WS behind nginx).
3. Nginx: `proxy_http_version 1.1`, `Upgrade`, `Connection "upgrade"` for `/ws/`.
4. Supervisor unit(s) updated in deploy docs (implementation change tracks config snippets in `support/docs/` / ops notes—not inventing untracked prod files blindly).

**Why:** Current Gunicorn-only WSGI cannot serve Channels WebSockets correctly.

### 11. REST paths (aligned with repo)

| Role | Paths |
|------|--------|
| Customer | `GET /api/v1/support/inbox/`, `POST /api/v1/support/messages/` |
| Admin | `GET/PATCH/POST` under `/api/v1/web/support/conversations/...` |

### 12. Package layout

```text
support/
  models.py
  admin.py
  api/           # REST
  realtime/      # consumers.py, middleware.py, routing.py
  services/      # conversations, messages, presence, notifications
  tests/
  docs/frontend/
```

## Risks / Trade-offs

- **[Risk] Production still WSGI-only** → Mitigation: treat ASGI + Redis + nginx WS as hard deploy prerequisites; feature flag or docs gate before mobile enablement.
- **[Risk] Token in query string logged by proxies** → Mitigation: prefer short-lived tokens later; document HTTPS-only; avoid logging full query in app logs.
- **[Risk] Duplicate messages if client uses REST + WS send** → Mitigation: single service API; clients use one primary send path; idempotency key optional later.
- **[Risk] Presence false positives/negatives** → Mitigation: TTL + heartbeat; UI treats presence as soft signal.
- **[Risk] Admin email spam on every customer message** → Mitigation: only when no admin presence on support channels; optional debounce later.
- **[Risk] Scope creep vs earlier poll-only plan** → Mitigation: this design supersedes non-realtime non-goals; out-of-scope media/voice remains firm.

## Migration Plan

1. Add dependencies + Redis env; migrate models.
2. Ship REST first (usable without WS).
3. Enable Channels routing + consumers; local Redis.
4. Deploy ASGI + nginx `/ws/`; verify connect/auth.
5. Enable offline FCM/email hooks.
6. Rollback: disable WS route / revert ASGI mount; REST inbox still works; tables retained.

## Open Questions

- Prefer **split** Gunicorn (HTTP) + Daphne (WS) vs **single** Uvicorn/Daphne for all traffic? Default recommendation: **split** to minimize blast radius on existing Gunicorn deploy, unless ops prefers one ASGI service.
- Customer “support online” = any admin connected to **this** conversation vs any admin in **global agents** set? Default: **global agents presence** OR conversation-local—product can pick; implement **conversation-local + optional global admin inbox presence** for list green dots.
- Exact mobile WS auth: query `token` vs header—confirm with mobile app constraints; document one primary method.
