## Context

### Current notification-related architecture

| Layer | Location | State |
|-------|----------|-------|
| Device token storage | `user_management/models.py` → `DeviceToken` | Production-ready |
| Token register/remove API | `notifications/api/device_token_views.py` | Mounted |
| Token query services | `notifications/services/device_service.py` | Ready |
| FCM send stub | `notifications/services/fcm_service.py` | Not configured |
| In-app `Notification` | `notifications/models.py` | Scaffold only |
| Firebase config | `core/settings/base.py` → `FIREBASE_CREDENTIALS` | Path only |
| Admin auth | `IsVerifiedAdmin` | Used across `/api/v1/web/*` |
| Async jobs | Celery in requirements | Not configured |

### Recommended architecture

```text
Admin Panel
    |
    |  POST /api/v1/web/notifications/send/
    v
NotificationSender (thin view)
    |
    +---> Target Resolver (notification_filter)
    |         └── CustomerProfile-only users
    |
    +---> Campaign Create (PushCampaign, status=processing)
    |
    +---> Recipients bulk_create (PushCampaignRecipient)
    |
    +---> Return 202 Accepted immediately
    |
    v (async — thread or management command)
FCM Service (fcm_service)
    |
    v
Firebase Cloud Messaging
    |
    v
Mobile Devices
    |
    v
Delivery Result → PushCampaignRecipient update → PushCampaign counters
```

All new code lives in the existing `notifications/` app:

```text
notifications/
├── models.py
├── services/
│   ├── device_service.py          # reuse
│   ├── fcm_service.py             # implement
│   ├── notification_filter.py     # NEW
│   └── notification_sender.py     # NEW
├── management/commands/
│   └── dispatch_push_campaign.py  # NEW — production dispatch entry
├── api/
│   ├── web_urls.py
│   ├── admin_notification_views.py
│   ├── admin_notification_serializers.py
│   └── openapi.py
└── docs/
    ├── backend/admin-push-notifications.md
    └── frontend/admin-push-notifications.md
```

Mount: `path('api/v1/web/notifications/', include('notifications.api.web_urls'))`

### Model naming

| User term | Implementation | Rationale |
|-----------|----------------|-----------|
| Notification (campaign) | `PushCampaign` | Avoid breaking in-app `Notification` scaffold |
| NotificationRecipient | `PushCampaignRecipient` | Per-user/device delivery audit |

## Goals / Non-Goals

**Goals:**

- Verified admins send FCM push to customers only (single, selected, filtered, all)
- **Async-first HTTP contract** — POST returns `202 Accepted` immediately; no blocking on 10,000-user broadcasts
- **Idempotency** — prevent duplicate campaigns from double-clicks or slow networks
- Recipient statuses: `pending`, `sent`, `failed`, `skipped`
- Campaign partial failure: `status=completed` with `total_failed > 0` when some deliveries fail
- Strict Flutter deep-link payload contract (`screen`, `entity_type`, `entity_id`)
- Firebase via `settings.FIREBASE_CREDENTIALS`; multi-process-safe init
- Broadcast audit: `created_by`, `ip_address`, `user_agent`
- Batch FCM send (500 tokens), bulk DB ops, no N+1
- Admin history list + detail APIs
- Explicit admin panel frontend UX spec

**Non-Goals:**

- Celery worker setup (management command + daemon thread for MVP)
- Customer in-app notification inbox changes
- SMS/email channels
- Notification analytics dashboard (future)
- Automatic retry scheduler (future — fields reserved in design)

## Decisions

### 1. Database design

#### `PushCampaign`

| Field | Type | Notes |
|-------|------|-------|
| `public_id` | UUID | `PublicIdMixin` |
| `title` | CharField(255) | |
| `body` | TextField | max 4000 |
| `notification_type` | CharField | `order`, `wallet`, `delivery`, `promotion`, `system` |
| `data` | JSONField | Allowlisted deep-link keys only (see §2) |
| `created_by` | FK → User | Admin initiator |
| `ip_address` | GenericIPAddressField null | Audit |
| `user_agent` | CharField(512) blank | Audit |
| `idempotency_key` | CharField(128) blank | From `Idempotency-Key` header |
| `target_type` | CharField | `single_user`, `selected_users`, `filtered_users`, `all_users` |
| `target_config` | JSONField | Snapshot of targeting input |
| `status` | CharField | `pending`, `processing`, `completed`, `failed` |
| `total_targets` | PositiveIntegerField | User count |
| `total_sent` | PositiveIntegerField | Default 0 |
| `total_failed` | PositiveIntegerField | Default 0 |
| `total_skipped` | PositiveIntegerField | Default 0 — push preference opt-outs |
| `error_summary` | TextField blank | Set only when campaign-level failure (e.g. Firebase not configured) |
| `created_at`, `updated_at` | DateTimeField | |

**Indexes:** `(status, created_at)`, `(created_by, created_at)`, unique partial on `(idempotency_key, created_by)` where key non-empty, fingerprint index for duplicate detection

**Partial failure semantics:**

| Outcome | `status` | Counters |
|---------|----------|----------|
| All recipients sent | `completed` | `total_failed=0`, `total_skipped=0` |
| Mix of sent/failed/skipped | `completed` | `total_failed > 0` and/or `total_skipped > 0` |
| Firebase not configured / unrecoverable campaign error | `failed` | `error_summary` set |

Do **not** add `completed_with_errors` enum — use `completed` + counter fields. Document in API and frontend docs that `total_failed > 0` means partial delivery errors.

#### `PushCampaignRecipient`

| Field | Type | Notes |
|-------|------|-------|
| `campaign` | FK → PushCampaign | |
| `user` | FK → User | |
| `device` | FK → DeviceToken null | |
| `status` | CharField | `pending`, `sent`, `failed`, `skipped` |
| `firebase_message_id` | CharField blank | |
| `error_message` | TextField blank | |
| `sent_at` | DateTimeField null | |

**Future fields (not in MVP migration, documented for retry follow-up):**

- `retry_count` — integer, default 0
- `last_error` — text, last transient FCM error
- `next_retry_at` — datetime, for scheduled retry worker

**Indexes:** `(campaign, status)`, `(user, sent_at)`, `(status, campaign)`

**Recipient rules:**

- One row per (user, active device) when sending
- No active device → `status=failed`, `error_message='No active device'`
- `NotificationPreference.push_enabled=False` → `status=skipped`, `error_message='Push notifications disabled by user'`
- `skipped` is **not** a failure — excluded from `total_failed`, counted in `total_skipped`

### 2. API design

Base path: `/api/v1/web/notifications/`. All endpoints: `IsVerifiedAdmin`.

#### POST `/send/` — Create campaign (async)

**Request:**

```json
{
  "title": "Special Offer",
  "body": "20% discount today",
  "notification_type": "promotion",
  "data": {
    "screen": "promotion_detail",
    "entity_type": "promotion",
    "entity_id": "summer-sale"
  },
  "target": { "type": "all", "confirm_broadcast": true }
}
```

**Headers:**

```http
Authorization: Token <admin-token>
Idempotency-Key: <uuid-or-client-generated-key>   # recommended
```

**FCM data payload contract (strict allowlist):**

| Key | Required | Description |
|-----|----------|-------------|
| `screen` | Recommended | Flutter route name, e.g. `order_detail`, `wallet`, `promotion_detail` |
| `entity_type` | Recommended | Domain entity, e.g. `order`, `wallet_transaction`, `promotion` |
| `entity_id` | Optional | String identifier for deep link |

Rules:

- Only allowlisted keys permitted in `data` — reject unknown keys with `400`
- All values MUST be strings (FCM requirement)
- Max serialized size 4 KB
- `notification_type` in request body drives notification channel/category; `data.screen` drives Flutter navigation

Legacy `{type, id}` shape is **not** accepted — use `entity_type` / `entity_id`.

**Response — always `202 Accepted`:**

```json
{
  "public_id": "abc-uuid",
  "status": "processing",
  "total_targets": 5000
}
```

Admin panel polls `GET /{public_id}/` until `status` is `completed` or `failed`.

**Never block HTTP** waiting for FCM dispatch — even for 100-user sends.

#### Targeting

| `target.type` | Fields | Maps to |
|---------------|--------|---------|
| `user` | `user_id` | `single_user` |
| `users` | `user_ids` (max 500) | `selected_users` |
| `filter` | `filters` | `filtered_users` |
| `all` | `confirm_broadcast` when count > threshold | `all_users` |

**Customer-only validation:**

Every resolved target user MUST have an associated `CustomerProfile`. Reject or silently exclude (prefer reject with `422` for explicit `user`/`users` targets):

- Staff users
- Rider (`RiderProfile`) users
- Admin users (`AdminProfile`)
- Users without any customer profile

For `user`/`users` mode: if any ID is non-customer → `422` with list of invalid IDs.

#### Idempotency (must have)

Two layers:

1. **`Idempotency-Key` header** — if provided, return existing campaign response (same status code `202`) when the same admin reuses the key within 24 hours
2. **Fingerprint dedup** — within 5 minutes, block duplicate campaigns with identical `title`, `body`, normalized `target`, and `created_by` → respond `409 Conflict` with existing `public_id`

Store `idempotency_key` on `PushCampaign` row.

#### GET `/` — History

Paginated. Columns for admin list: Title, Type, Target, Status, Sent, Failed, Skipped, Created By, Date.

#### GET `/{public_id}/` — Detail

Campaign info + paginated recipients with: user email, device platform, status (`sent`/`failed`/`skipped`), `firebase_message_id`, `error_message`, `sent_at`.

### 3. Async dispatch (MVP without Celery)

**Flow:**

```text
POST /send/
  → validate + idempotency check
  → create PushCampaign (status=processing)
  → resolve targets + bulk_create recipients
  → enqueue dispatch (non-blocking)
  → return 202

dispatch_push_campaign(campaign_id):
  → status stays processing
  → FCM batches (500 tokens)
  → update recipients + counters
  → status = completed | failed
```

**MVP dispatch triggers (both implemented):**

1. **Daemon thread** — `threading.Thread(target=dispatch_push_campaign, args=(campaign_id,), daemon=True).start()` immediately after 202 response. Suitable for dev and moderate traffic.
2. **Management command** — `python manage.py dispatch_push_campaign --campaign-id=<public_id>` for production cron/worker until Celery exists. Also processes any stuck `processing` campaigns.

Service function `dispatch_push_campaign(campaign_id)` is the single dispatch entry — callable from thread, management command, or future Celery task.

### 4. Firebase initialization (multi-process safe)

```python
import firebase_admin
from firebase_admin import credentials

def _get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        return firebase_admin.initialize_app(cred)
```

Never call `initialize_app()` without checking `get_app()` first — prevents "Firebase app already exists" in multi-worker Gunicorn/uWSGI deployments.

### 5. Service architecture

**`notification_filter.py`:**

- `resolve_target_users(target) → QuerySet[User]` — inner join / filter on `CustomerProfile`
- `validate_customer_user_ids(user_ids) → raises 422 for staff/rider/admin`
- Reuse admin customer filter allowlist

**`notification_sender.py`:**

- `create_campaign(...) → PushCampaign` — atomic create + recipients
- `enqueue_dispatch(campaign_id)` — thread spawn
- `dispatch_push_campaign(campaign_id)` — full FCM loop

**`fcm_service.py`:**

- Multi-process-safe init
- `send_to_token`, `send_to_tokens` (500 batch)
- Invalid token → `device_service.deactivate_device_token_by_value()`

### 6. Security

- `IsVerifiedAdmin` on all endpoints
- Customer-only targets enforced in filter layer
- Audit: `ip_address` from `request.META['REMOTE_ADDR']`, `user_agent` from `HTTP_USER_AGENT`
- Do not log FCM tokens or credentials
- Broadcast guard: `confirm_broadcast: true` when eligible count > threshold (default 1000)

### 7. Admin workflow

```text
1. Admin login → Token
2. Send page: title, body, type, data (screen/entity_type/entity_id), target mode
3. Preview panel (client-side): show title/body + estimated target count
4. POST /send/ with Idempotency-Key → 202 processing
5. UI polls GET /{public_id}/ every 2–3s until completed/failed
6. Show sent/failed/skipped counts
7. History list → detail for recipient breakdown
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Daemon thread lost on process restart | Management command re-processes stuck `processing` campaigns; document cron setup |
| Duplicate admin clicks | Idempotency-Key + 5-minute fingerprint dedup |
| Partial FCM failure unclear to admin | `completed` + `total_failed`/`total_skipped`; detail page shows per-recipient status |
| Non-customer targeted by ID | Explicit 422 validation for user/users modes |
| Firebase app already exists | `get_app()` guard before init |
| Transient FCM network errors counted as failed | Future retry via `retry_count`/`last_error`; document in ops runbook |

## Migration Plan

1. Add models + migration
2. Implement services + management command
3. Mount web URLs
4. Configure cron: `*/1 * * * * manage.py dispatch_push_campaign --stuck-only`
5. Smoke test single-device send

## Open Questions

- Daily broadcast limit per admin? **Defer** — ops runbook; add throttle in follow-up.
- Notification analytics (open rate)? **Out of scope** — future capability.
