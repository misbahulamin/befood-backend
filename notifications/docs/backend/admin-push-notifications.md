# Admin Push Notifications — Backend Technical Guide

## Summary

Verified admins send Firebase Cloud Messaging (FCM) push notifications to **customers only** via async campaign APIs. The HTTP send endpoint returns **`202 Accepted`** immediately; FCM dispatch runs in a background thread (MVP) or via management command / future Celery worker.

## Endpoint grid

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/web/notifications/send/` | Verified admin | Create campaign, return 202 |
| GET | `/api/v1/web/notifications/` | Verified admin | Paginated campaign history |
| GET | `/api/v1/web/notifications/{public_id}/` | Verified admin | Campaign detail + recipients |

## Permissions

| Actor | Send | List | Detail |
|-------|------|------|--------|
| Unauthenticated | 401 | 401 | 401 |
| Customer | 403 | 403 | 403 |
| Verified admin | 202 | 200 | 200 |

Permission class: `IsVerifiedAdmin` (`user_management/api/permissions.py`).

## Key models

| Model | Purpose |
|-------|---------|
| `PushCampaign` | Admin broadcast lifecycle, counters, audit fields |
| `PushCampaignRecipient` | Per-user/device delivery row |
| `DeviceToken` (`user_management`) | Reused for FCM tokens — not duplicated |

### Campaign status

| Status | Meaning |
|--------|---------|
| `processing` | Created; dispatch running or queued |
| `completed` | Dispatch finished (may include partial failures) |
| `failed` | Unrecoverable error (e.g. Firebase not configured) |

**Partial failure:** `status=completed` with `total_failed > 0`. This is not campaign-level failure.

### Recipient status

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for FCM |
| `sent` | Delivered to FCM |
| `failed` | FCM or device error |
| `skipped` | User opted out (`NotificationPreference.push_enabled=False`) |

## Service flow

```text
POST /send/
  → validate + idempotency check
  → resolve customer targets (notification_filter)
  → create PushCampaign + PushCampaignRecipient rows
  → enqueue dispatch (daemon thread)
  → return 202

dispatch_push_campaign(campaign_id)
  → FCM batches (500 tokens)
  → update recipients + counters
  → status = completed | failed
```

Services:

- `notifications/services/notification_filter.py` — targeting
- `notifications/services/notification_sender.py` — campaign + dispatch
- `notifications/services/fcm_service.py` — Firebase send
- `notifications/services/device_service.py` — token storage/deactivation

## Idempotency

1. **`Idempotency-Key` header** — same admin + key within 24h returns existing campaign (`202`)
2. **Fingerprint dedup** — identical title/body/target within 5 minutes → `409 Conflict`

## Firebase configuration

Set credentials path in settings (already configured):

```python
FIREBASE_CREDENTIALS = BASE_DIR / 'credentials' / 'firebase_service_account.json'
```

Do not commit credential files. Firebase init uses `firebase_admin.get_app()` guard for multi-worker safety.

## Management command

```bash
# Dispatch one campaign
python manage.py dispatch_push_campaign --campaign-id=<public_id>

# Recover stuck processing campaigns
python manage.py dispatch_push_campaign --stuck-only
```

Recommended cron (production):

```text
*/5 * * * * python manage.py dispatch_push_campaign --stuck-only
```

## FCM data payload contract

Allowlisted keys only (string values):

| Key | Example |
|-----|---------|
| `screen` | `order_detail` |
| `entity_type` | `order` |
| `entity_id` | `123` |

## Verification

```bash
python manage.py test notifications.tests.test_admin_push_notifications notifications.tests.test_device_token --keepdb
python manage.py spectacular --file schema.yaml
```

## Related docs

- Device token registration: `notifications/docs/backend/fcm-device-token.md`
- Frontend admin guide: `notifications/docs/frontend/admin-push-notifications.md`
