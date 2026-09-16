## 1. Infrastructure prerequisites

- [x] 1.1 Add dependencies: `channels`, `channels-redis`, `daphne` (pin compatible versions with Django 5.2) to `requirements.txt`
- [x] 1.2 Document/require Redis URL env (e.g. `REDIS_URL` / `CHANNEL_REDIS_URL`) for channel layer + presence keys
- [x] 1.3 Configure `CHANNEL_LAYERS` Redis backend in settings; keep test override documented
- [x] 1.4 Replace bare `core.asgi` with Channels `ProtocolTypeRouter` (HTTP + WebSocket URLRouter)
- [x] 1.5 Document production process model (Gunicorn HTTP + Daphne/Uvicorn WS **or** full ASGI) and nginx `/ws/` Upgrade headers

## 2. App scaffold & models

- [x] 2.1 Create Django app `support` (`models`, `admin`, `api/`, `realtime/`, `services/`, `tests/`, `docs/frontend/`)
- [x] 2.2 Register `support` (+ Channels) in `INSTALLED_APPS`
- [x] 2.3 Implement `SupportConversation` (PublicIdMixin, OneToOne CustomerProfile, status, last_message, last_message_at, unread counters, timestamps)
- [x] 2.4 Implement `SupportMessage` (PublicIdMixin, FK, sender_type, sender_user, body, is_read_by_customer, is_read_by_admin, created_at, indexes)
- [x] 2.5 Generate migration and register read-focused Django admin

## 3. Domain services (shared REST + WS write path)

- [x] 3.1 Get-or-create conversation by customer profile
- [x] 3.2 Post message service (customer/admin/system): atomic persist, denormalize last message, adjust unread
- [x] 3.3 Mark-read service for customer and admin sides; status update service (open/closed/archived)
- [x] 3.4 Admin list queryset: pagination helpers, `status`, `has_unread`, `q` search, deterministic ordering
- [x] 3.5 After persist: `group_send` conversation events; optional admin-inbox group bump

## 4. Customer & admin REST APIs

- [x] 4.1 Customer `GET /api/v1/support/inbox/` and `POST /api/v1/support/messages/` (`HasCustomerProfile`, pagination, OpenAPI)
- [x] 4.2 Admin `GET /api/v1/web/support/conversations/` list with search/filters (`IsVerifiedAdmin`)
- [x] 4.3 Admin detail `GET .../{public_id}/`, reply `POST .../reply/`, status `PATCH .../status/`
- [x] 4.4 Mount urls in `core/urls.py` (`/api/v1/support/`, `/api/v1/web/support/`)

## 5. WebSocket auth, routing, messaging

- [x] 5.1 Token auth middleware for WebSocket (document query/header contract; HTTPS-only)
- [x] 5.2 Consumer ACL: customer → own conversation only; verified admin → any conversation (+ optional admin inbox group)
- [x] 5.3 Implement `/ws/support/<conversation_public_id>/` routing
- [x] 5.4 Handle `message.send` → shared persist → broadcast `message.receive`
- [x] 5.5 Handle `message.read` → mark-read service → broadcast read update
- [x] 5.6 Reject unauthenticated connects and cross-customer joins

## 6. Typing & presence

- [x] 6.1 Relay `typing.start` / `typing.stop` to conversation group without DB writes
- [x] 6.2 Presence on connect/disconnect (+ optional heartbeat) via Redis TTL keys
- [x] 6.3 Broadcast `presence.online` / `presence.offline` to authorized peers; expose presence hints on admin list when cheap

## 7. Offline notifications (reuse FCM/email)

- [x] 7.1 On admin reply: if customer not present → `create_inbox_notification` + FCM; if present → skip push (still persist)
- [x] 7.2 On customer message: if no admin support presence → email verified admins (funding-style recipients); best-effort `on_commit`
- [x] 7.3 Ensure failures never roll back `SupportMessage`

## 8. Tests

- [x] 8.1 REST: customer send/inbox, one conversation, validation, admin list/filter/reply/status, authz/BOLA
- [x] 8.2 WebSocket: auth reject, ACL deny, message.send/receive between customer and admin (Channels test client)
- [x] 8.3 Typing events do not create DB rows; presence connect/disconnect behavior
- [x] 8.4 Offline notification scheduling when presence absent; skip when present; SMTP/FCM failure isolation
- [x] 8.5 Run `python manage.py check` and support test suite

## 9. Docs & ops reportables

- [x] 9.1 Write `support/docs/frontend/support-inbox.md` (REST + WS events, auth, payloads, admin UI list/chat layout notes)
- [x] 9.2 Document new dependencies, Redis setup, migration commands, WebSocket URL, nginx/ASGI deploy steps, and manual test checklist
