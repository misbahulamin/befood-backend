# Admin Push Notifications — Backend Technical Guide

## Summary

Verified admins send Firebase Cloud Messaging (FCM) push notifications to **customers only** via async campaign APIs. The HTTP send endpoint returns **`202 Accepted`** immediately; FCM dispatch runs in a background thread (MVP) or via management command / future Celery worker.

Admin campaigns also create **customer inbox** rows (Flutter app / `app.befood.com.bd`). Inbox visibility is **independent** of FCM success — see [Inbox vs FCM `sent`](#inbox-vs-fcm-sent).

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
| `Notification` | Customer inbox row; campaign dispatch sets GFK → `PushCampaign` for read audit |
| `DeviceToken` (`user_management`) | Reused for FCM tokens — not duplicated (`token` max length **512**) |

### Detail recipient fields

Each recipient on `GET .../{public_id}/` includes:

- `user_email`, `user_name`, `user_public_id` (`CustomerProfile.public_id` or null)
- `device_platform`, `status`, `error_message`, `firebase_message_id`, `sent_at`
- `is_read` — from linked inbox `Notification` (boolean), or `null` if no GFK-linked inbox row

### Campaign status

| Status | Meaning |
|--------|---------|
| `processing` | Created; dispatch running or queued |
| `completed` | Dispatch finished (may include partial failures / zero FCM successes) |
| `failed` | Unrecoverable error (e.g. Firebase not configured, or unexpected send crash with zero successes) |

**Partial failure:** `status=completed` with `total_failed > 0`. This is not campaign-level failure.

Dispatch **must** leave every campaign in `completed` or `failed`. Unexpected FCM/SDK errors finalize remaining `pending` recipients and never leave `processing`.

### Recipient status

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for FCM |
| `sent` | Delivered to FCM |
| `failed` | FCM or device error |
| `skipped` | User opted out (`NotificationPreference.push_enabled=False`) |

## Inbox vs FCM `sent`

| Channel | What it is | When it is created / counted |
|---------|------------|------------------------------|
| **Customer inbox** | API-backed list in Flutter app / web (`app.befood.com.bd`) | One unread `Notification` per distinct non-skipped target user, **before** FCM send. Created even when the user has no active device token or FCM later fails. |
| **Admin `total_sent`** | FCM delivery counter on the campaign | Increments **only** when FCM reports success for a recipient token. Inbox alone never increments `total_sent`. |

Implications for operators:

- Web inbox can show a message while admin poll shows `total_sent=0` (all FCM attempts failed, or no active tokens).
- Multi-device customers get **one** inbox row; FCM is attempted per active token.
- Re-dispatch (`--stuck-only`) **dedupes** inbox by user + campaign GFK — no duplicate inbox rows.

## Service flow

```text
POST /send/
  → validate + idempotency check
  → resolve customer targets (notification_filter)
  → create PushCampaign + PushCampaignRecipient rows
  → enqueue dispatch (daemon thread)
  → return 202

dispatch_push_campaign(campaign_id)
  → create inbox Notification per unique non-skipped user (GFK → campaign; dedupe on re-run)
  → platform-split FCM batches (native android/ios vs web), chunk size 500
  → update recipients + counters (total_sent = FCM successes only)
  → on unexpected error: fail remaining pending, set completed|failed
  → status = completed | failed  (never stuck processing after the attempt ends)
```

### Platform-split FCM

`fcm_service.send_to_tokens` splits tokens by `DeviceToken.platform`:

| Platform | Message config |
|----------|----------------|
| `android` / `ios` (native) | `AndroidConfig` (channel + high priority) — **no** `WebpushConfig` |
| `web` | `WebpushConfig` click link — separate batch |

A web-only configuration failure does not prevent successful delivery to valid native tokens in the same campaign. Per-token success/failure is recorded independently.

Invalid-token deactivation is **narrow**: only clearly unregistered / not-found registration-token errors soft-deactivate devices. Broad markers such as generic `invalid-argument` (often payload/config mistakes) do **not** deactivate tokens.

Services:

- `notifications/services/notification_filter.py` — targeting
- `notifications/services/notification_sender.py` — campaign + dispatch
- `notifications/services/fcm_service.py` — Firebase send
- `notifications/services/device_service.py` — token storage/deactivation
- `notifications/services/inbox_service.py` — inbox persistence + campaign dedupe

## Idempotency

1. **`Idempotency-Key` header** — same admin + key within 24h returns existing campaign (`202`)
2. **Fingerprint dedup** — identical title/body/target within 5 minutes → `409 Conflict`

## Firebase configuration

Set credentials path in settings (already configured):

```python
FIREBASE_CREDENTIALS = BASE_DIR / 'credentials' / 'firebase_service_account.json'
```

Do not commit credential files. Firebase init uses `firebase_admin.get_app()` guard for multi-worker safety.

For browser system notifications (beyond inbox), the Firebase project must have **web push certificates / VAPID** configured. Native Android/iOS batches still succeed if web credentials are missing.

## Device token length (production deploy)

Web / PWA FCM tokens can exceed 255 characters. Ensure migration is applied:

```bash
python manage.py migrate user_management 0025_device_token_length_512
# or full: python manage.py migrate
```

| Layer | Max token length |
|-------|------------------|
| `DeviceToken.token` column | 512 |
| API serializer + `device_service` | 512 |

## Management command / stuck recovery

```bash
# Dispatch one campaign
python manage.py dispatch_push_campaign --campaign-id=<public_id>

# Recover stuck processing campaigns (updated_at older than 30 minutes)
python manage.py dispatch_push_campaign --stuck-only
```

Recommended cron (production):

```text
*/5 * * * * python manage.py dispatch_push_campaign --stuck-only
```

`--stuck-only` re-enters the hardened dispatcher: remaining `pending` recipients are sent; inbox rows for users who already have a campaign-linked notification are not duplicated.

## FCM data payload contract

Allowlisted keys only (string values):

| Key | Example |
|-----|---------|
| `screen` | `order_detail` |
| `entity_type` | `order` |
| `entity_id` | `123` |

## Manual verification checklist (after deploy)

1. Confirm `user_management.0025_device_token_length_512` is applied on production.
2. Send a **single-user** campaign to a known Android device → system tray push arrives.
3. Open the same user's session on `app.befood.com.bd` → message appears in notification inbox.
4. Poll admin detail until terminal `status` (`completed` or `failed`) with accurate `total_sent` / `total_failed`.
5. If any campaign remains `processing` > 30 minutes, run `dispatch_push_campaign --stuck-only` and re-check.

## Verification (automated)

```bash
python manage.py test notifications.tests.test_admin_push_notifications notifications.tests.test_notification_inbox notifications.tests.test_device_token --keepdb
python manage.py spectacular --file schema.yaml
```

## Related docs

- Device token registration: `notifications/docs/backend/fcm-device-token.md`
- Frontend admin guide: `notifications/docs/frontend/admin-push-notifications.md`
