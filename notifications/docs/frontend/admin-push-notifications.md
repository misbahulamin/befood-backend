# Admin Push Notifications — Frontend Integration Guide

## Overview

The admin panel sends push notifications to customers through three API endpoints. Sending is **async**: POST returns `202 Accepted` with `status: processing`; the UI polls the detail endpoint until completion.

## Authentication

```http
Authorization: Token <admin-token>
Idempotency-Key: <uuid-per-send-attempt>   # recommended
```

Admin must be a verified admin (`IsVerifiedAdmin`).

---

## Workflow (step-by-step)

1. Admin logs in → `POST /user_management/admin/login/`
2. Open **Send Notification** page → compose form
3. Preview title/body and estimated target count (client-side)
4. `POST /api/v1/web/notifications/send/` → receive `202` with `public_id`
5. Poll `GET /api/v1/web/notifications/{public_id}/` every 2–3s until `status` is `completed` or `failed`
6. Show sent / failed / skipped counts
7. View history via `GET /api/v1/web/notifications/`

---

## Send page fields

| Field | Type | Notes |
|-------|------|-------|
| Title | text | max 255 |
| Body | textarea | max 4000 |
| Notification Type | select | `order`, `wallet`, `delivery`, `promotion`, `system` |
| Target mode | tabs | See targeting section |
| Screen | text | Flutter route, e.g. `order_detail` |
| Entity Type | text | e.g. `order` |
| Entity ID | text | optional deep-link id |

**UX requirements:**

- Show preview panel before send
- Generate `Idempotency-Key` (UUID) per send attempt
- Disable Send button after click until response received
- Show broadcast confirmation modal when eligible count > threshold

---

## Targeting modes

### Single user

```json
{
  "target": { "type": "user", "user_id": 123 }
}
```

Use admin customer search to resolve `user_id`. Only customers with `CustomerProfile` are valid.

### Multiple users

```json
{
  "target": { "type": "users", "user_ids": [1, 2, 3] }
}
```

Max 500 IDs per request.

### Filter

```json
{
  "target": {
    "type": "filter",
    "filters": {
      "is_active": true,
      "is_email_verified": true,
      "registered_from": "2026-01-01",
      "registered_to": "2026-12-31",
      "has_active_subscription": true,
      "has_wallet": true,
      "service_area_public_id": "uuid"
    }
  }
}
```

Only allowlisted filter keys are accepted.

### All users (broadcast)

```json
{
  "target": { "type": "all", "confirm_broadcast": true }
}
```

When eligible count exceeds threshold (~1000), `confirm_broadcast: true` is required or API returns `422`.

---

## POST /api/v1/web/notifications/send/

### Request example

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
  "target": { "type": "user", "user_id": 123 }
}
```

### Success response — 202 Accepted

```json
{
  "public_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "total_targets": 1,
  "total_sent": 0,
  "total_failed": 0,
  "total_skipped": 0,
  "created_by_email": "admin@example.com",
  "created_at": "2026-09-02T10:00:00Z"
}
```

### Duplicate fingerprint — 409 Conflict

Same title/body/target within 5 minutes returns existing campaign body (same shape as 202).

### Error examples

| Status | Cause |
|--------|-------|
| 400 | Validation (unknown data keys, oversized title) |
| 403 | Not verified admin |
| 409 | Duplicate campaign (fingerprint dedup) |
| 422 | Non-customer user ID, broadcast confirmation required |

---

## Notification List page

Columns:

| Column | API field |
|--------|-----------|
| Title | `title` |
| Type | `notification_type` |
| Target | `target_type` |
| Status | `status` |
| Sent | `total_sent` |
| Failed | `total_failed` |
| Skipped | `total_skipped` |
| Created By | `created_by_email` |
| Date | `created_at` |

**Partial failure UI:** when `status=completed` and `total_failed > 0`, show failed count prominently (amber/warning), not as full failure.

Filters: `status`, `notification_type`, `created_from`, `created_to`

---

## Detail page

Show campaign info + recipients table:

| Column | Field |
|--------|-------|
| User | `user_email` |
| Platform | `device_platform` |
| Status | `status` (`sent` / `failed` / `skipped`) |
| Error | `error_message` |
| FCM Message ID | `firebase_message_id` |
| Sent at | `sent_at` |

**Skipped recipients:** use neutral styling — label "Push disabled by user", not error red.

**Polling:** while `status=processing`, poll detail every 2–3 seconds.

Summary chips: Sent / Failed / Skipped counts.

---

## Flutter deep-link payload

FCM `data` keys consumed by mobile app:

```json
{
  "screen": "order_detail",
  "entity_type": "order",
  "entity_id": "123"
}
```

| notification_type | Suggested screen |
|-------------------|------------------|
| order | `order_detail` |
| wallet | `wallet` |
| delivery | `delivery_tracking` |
| promotion | `promotion_detail` |
| system | `home` |

---

## Error handling checklist

- [ ] Handle 409 duplicate — show "Already sent" with link to existing campaign
- [ ] Handle 422 non-customer target — show validation message
- [ ] Handle processing timeout — suggest checking history list
- [ ] Never retry send without new `Idempotency-Key` unless intentional
