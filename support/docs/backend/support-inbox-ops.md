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

Migrations:

- `support/migrations/0001_support_conversation_message.py`
- `support/migrations/0002_last_message_sender_nulls_last_ordering.py` — adds `last_message_sender`; replaces list index with `last_message_at DESC NULLS LAST, id DESC` on PostgreSQL (SQLite gets a plain composite index; ORM still orders nulls last)

Models:

- `SupportConversation` — one per `CustomerProfile`; denormalized `last_message_sender` (`customer` \| `admin` \| null)
- `SupportMessage` — immutable history

Admin list defaults: exclude `last_message_at IS NULL` unless `include_empty=true`.

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

## WebSocket URLs

```text
# Admin inbox fan-out (verified admin only; no conversation required)
ws://<host>/ws/support/inbox/?token=<drf-token>
wss://<host>/ws/support/inbox/?token=<drf-token>

# Per-conversation chat
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
