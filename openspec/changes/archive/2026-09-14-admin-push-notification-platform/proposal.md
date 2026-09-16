## Why

Verified admins need a production-ready way to send Firebase Cloud Messaging (FCM) push notifications to customers — to one user, selected users, filtered cohorts, or all eligible users — with auditable delivery history. The backend already has `DeviceToken` storage, device registration APIs, and a stub `fcm_service.py`, but no admin send workflow, no campaign/delivery tracking models, and no Firebase Admin SDK integration. Without this platform, marketing, order, wallet, and system alerts cannot be delivered reliably at scale.

Large broadcasts (10,000+ users) must not block HTTP requests — duplicate sends from admin double-clicks must be prevented — and Flutter clients need a predictable deep-link payload contract.

## What Changes

- **Firebase Admin SDK integration** in `notifications/services/fcm_service.py` using existing `settings.FIREBASE_CREDENTIALS` with multi-process-safe init (`firebase_admin.get_app()` check)
- **New campaign models** `PushCampaign` and `PushCampaignRecipient` for admin broadcast lifecycle and per-user/device delivery tracking (avoids breaking the existing in-app `Notification` scaffold)
- **Async-first send response**: `POST /send/` returns `202 Accepted` immediately with `status: processing`; FCM dispatch runs out-of-band via in-process thread (MVP) and `manage.py dispatch_push_campaign` management command (production path until Celery is configured)
- **Idempotency protection** on send: `Idempotency-Key` request header plus 5-minute duplicate fingerprint block (same `title`, `body`, `target`, `created_by`)
- **Service layer** for targeting, batch sending, and invalid-token cleanup:
  - `notification_filter.py` — resolve target users/devices; only users with `CustomerProfile` (reject staff, rider, admin targets)
  - `notification_sender.py` — orchestrate campaign creation, recipient bulk insert, async dispatch trigger
  - Reuse `device_service.py` for active token queries
- **Strict FCM data payload contract** — allowlisted keys: `screen`, `entity_type`, `entity_id` (all string values) for predictable Flutter routing
- **Recipient status `skipped`** for users who opted out via `NotificationPreference.push_enabled=False` (distinct from `failed`)
- **Campaign audit fields**: `created_by`, `ip_address`, `user_agent`, `idempotency_key`
- **Partial failure semantics**: campaign `status=completed` when dispatch finishes; `total_failed > 0` indicates partial errors (not campaign-level `failed`)
- **Verified-admin web APIs** under `/api/v1/web/notifications/` — send (202), list, detail
- **OpenAPI + backend/frontend docs** including explicit admin panel UX spec (list, send, detail pages)
- **Comprehensive tests**: permissions, targeting, non-customer rejection, idempotency, async response, Firebase mock, batching, skipped status

## Capabilities

### New Capabilities

- `push-campaign-storage`: `PushCampaign` and `PushCampaignRecipient` models with `skipped` status, audit fields, idempotency key, indexes, partial-failure counters (`total_sent`, `total_failed`, `total_skipped`)
- `push-firebase-delivery`: Firebase Admin SDK init (multi-worker safe), single/multicast send, invalid-token deactivation, 500-token batching; future retry fields documented
- `admin-push-notification-api`: Verified-admin async send (202), idempotency, customer-only targeting validation, list, detail, strict data payload contract
- `admin-push-notification-frontend-docs`: Admin panel UX spec — notification list, send page, detail page, async polling, preview, deep-link payload guide

### Modified Capabilities

- (none — existing in-app `Notification` scaffold remains unchanged; device token APIs from `fcm-device-token-management` are consumed, not modified)

## Impact

- **Backend (`befood-backend`)**:
  - `notifications/models.py` — add `PushCampaign`, `PushCampaignRecipient`
  - `notifications/services/` — implement `fcm_service.py`, `notification_sender.py`, `notification_filter.py`
  - `notifications/management/commands/dispatch_push_campaign.py` — background dispatch entry point
  - `notifications/api/` — admin views, serializers, `web_urls.py`, OpenAPI
  - `core/urls.py` — mount `/api/v1/web/notifications/`
  - `notifications/tests/` — expanded test matrix
  - `notifications/docs/backend/`, `notifications/docs/frontend/` — admin push docs with UX spec
- **Reuse (no duplication)**:
  - `user_management.models.DeviceToken` and `notifications/services/device_service.py`
  - `IsVerifiedAdmin` from `user_management/api/permissions.py`
  - `PublicIdMixin`, web admin ViewSet patterns from `admin_customer_views.py`
  - `FIREBASE_CREDENTIALS` from `core/settings/base.py`
- **Out of scope (follow-up)**:
  - Celery/Redis worker setup (management command + thread MVP replaces it)
  - Customer in-app notification inbox hardening
  - Notification analytics dashboard
  - Automatic FCM retry scheduler (design reserves `retry_count` / `last_error` fields for future)
  - Wallet/order system changes
