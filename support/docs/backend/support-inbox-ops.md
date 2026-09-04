# Support Inbox — Backend / Ops Notes

## New dependencies

Add / already listed in `requirements.txt`:

- `channels>=4.1,<5`
- `channels-redis>=4.2,<5`
- `daphne>=4.1,<5`

Install:

```bash
pip install -r requirements.txt
```

## Redis

Channel layer + presence cache need Redis in staging/production.

Env (either works; `CHANNEL_REDIS_URL` preferred):

```bash
CHANNEL_REDIS_URL=redis://127.0.0.1:6379/0
# or
REDIS_URL=redis://127.0.0.1:6379/0
```

Optional:

```bash
SUPPORT_PRESENCE_TTL_SECONDS=60
SUPPORT_MESSAGE_MAX_LENGTH=5000
```

Local tests use `InMemoryChannelLayer` automatically when `manage.py test` runs (`core.settings.local`).

## Migration

```bash
python manage.py migrate support
```

Created migration: `support/migrations/0001_support_conversation_message.py`

Models:

- `SupportConversation` — one per `CustomerProfile`
- `SupportMessage` — immutable history

## ASGI / process model

`core/asgi.py` uses Channels `ProtocolTypeRouter` (HTTP + WebSocket).

**Recommended production split (lowest blast radius):**

1. Keep **Gunicorn** for HTTP REST (existing).
2. Run **Daphne** (or Uvicorn) for WebSockets on the same ASGI app.
3. Nginx routes `/ws/` to Daphne with Upgrade headers; everything else to Gunicorn.

Example Daphne:

```bash
daphne -b 0.0.0.0 -p 8001 core.asgi:application
```

Example nginx snippet:

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
}
```

Alternatively run **all** traffic through Daphne/Uvicorn (single ASGI service).

`runserver` alone is not enough for multi-worker WS in production; use Daphne for `/ws/`.

## WebSocket URL

```text
ws://<host>/ws/support/<conversation_public_id>/?token=<drf-token>
wss://<host>/ws/support/<conversation_public_id>/?token=<drf-token>
```

## REST mounts

- Customer: `/api/v1/support/`
- Admin: `/api/v1/web/support/`

## Manual test checklist

1. `python manage.py check`
2. `python manage.py test support.tests`
3. Customer REST send + inbox
4. Admin list / detail / reply / status
5. WS connect with token; deny other customer
6. Typing does not create DB rows
7. Offline admin reply → FCM path (mock/credentials)
8. Offline customer message → admin email (mail outbox / SMTP)

## Frontend docs

See `support/docs/frontend/support-inbox.md` for mobile + admin panel contracts.
