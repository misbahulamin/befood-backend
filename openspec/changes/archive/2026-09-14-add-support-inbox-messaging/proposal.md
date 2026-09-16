## Why

Customers and admins need a professional Alibaba/Taobao-style support inbox with **live chat**: durable history plus instant message delivery, typing indicators, and online presence—without page refresh. Ad-hoc support (calls/social) loses history; a poll-only inbox cannot deliver that live experience. We will add a support domain with REST for history/bootstrap and Django Channels WebSockets for real-time events, while reusing existing Token auth, permissions, and FCM for offline alerts.

## What Changes

- Add Django app `support` with permanent `SupportConversation` (one per customer) and immutable `SupportMessage` rows (`customer` / `admin` / `system`); no client delete APIs.
- Customer REST: `GET /api/v1/support/inbox/`, `POST /api/v1/support/messages/` (history + fallback send).
- Admin REST under `/api/v1/web/support/...`: conversation list (search/filter/unread/status), detail, reply, status PATCH.
- Introduce **Django Channels** + **Redis channel layer** + authenticated WebSocket at `ws/.../support/{conversation_public_id}/` for `message.*`, `typing.*`, `presence.*`, `message.read`.
- Ephemeral **typing** and **presence** via WebSocket/Redis only (not permanent DB rows).
- Reuse existing FCM + `create_inbox_notification` when the **recipient is offline**; reuse admin email/ops alert pattern for offline admins as needed—no new notification platform.
- Deploy/runtime: extend ASGI routing; document Redis + nginx WebSocket upgrade + process model (Daphne/Uvicorn alongside or instead of pure Gunicorn WSGI for WS traffic).
- Frontend docs for admin SPA (list + chat pane) and mobile (REST + WS + FCM).

## Capabilities

### New Capabilities
- `customer-support-inbox`: Authenticated customer REST inbox (paginated history, unread) and fallback message create; owns one conversation.
- `admin-support-inbox`: Verified-admin web REST list/detail/reply/status with search, filters, unread, customer identity fields.
- `support-realtime-messaging`: Authenticated WebSocket transport for instant message send/receive on a conversation; broadcast to authorized participants only.
- `support-typing-presence`: Ephemeral typing start/stop and online/offline presence over WebSocket (Redis-backed); not persisted as message history.
- `support-message-notifications`: Offline-aware alerts via existing inbox + FCM (customer) and existing admin notification/email pattern when the peer is not connected on the support channel.

### Modified Capabilities
- (none in `openspec/specs/` main tree) — additive domain; notification list APIs unchanged aside from new `notification_type` / `screen` values for support deep-links.

## Impact

- **New app:** `support/` (`models`, `api/`, `consumers` or `realtime/`, `routing`, `services/`, tests, frontend docs).
- **Dependencies:** `channels`, `channels-redis`, ASGI server capable of WebSockets (`daphne` and/or `uvicorn`); Redis required for channel layer + presence keys (package `redis` already listed; server/config must be provisioned).
- **Runtime:** Replace bare `core.asgi` with Channels `ProtocolTypeRouter`; production today is **Gunicorn + supervisor + nginx** (WSGI)—WebSockets need ASGI worker(s) and nginx `Upgrade`/`Connection` proxy for `/ws/`.
- **Auth:** DRF Token for REST; WebSocket auth via token query/header middleware compatible with existing `TokenAuthentication`.
- **Permissions:** `HasCustomerProfile` / conversation ownership for customers; `IsVerifiedAdmin` for admin REST and admin WS joins.
- **Out of scope (v1):** voice, video, file/image attachments, multi-agent assignment, canned replies, customer-to-customer chat.
