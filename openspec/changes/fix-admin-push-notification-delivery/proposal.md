# Proposal

## Why

Admin push campaigns from [befood.com.bd/admin/notifications](https://befood.com.bd/admin/notifications) recently stick in `processing` with `sent=0` while customers still see the message in the Flutter web inbox at `app.befood.com.bd`. That split means in-app inbox persistence is succeeding, but Firebase Cloud Messaging (FCM) delivery and/or campaign status finalization are not—breaking the previous Android push path after the iOS/web PWA notification updates (`b5f465b`).

## What Changes

- Harden campaign dispatch so unexpected FCM/SDK errors never leave a campaign stuck in `processing` with misleading `sent=0` counters.
- Keep Android/iOS native FCM delivery correct when web push support is also present (platform-aware message construction; do not let web-only config break native sends).
- Preserve and clarify dual delivery channels: **FCM push** (system tray / browser push) vs **customer notification inbox** (API-backed list shown in the Flutter app/web UI).
- Ensure web (`platform=web`) tokens used by the Flutter web build on `app.befood.com.bd` can be registered (token length up to 512) and targeted without harming Android tokens.
- Make stuck-campaign recovery reliable via the existing management command path and document operator verification for Android + web.
- Update related OpenAPI/backend docs and tests so admin `sent`/`failed`/`status` match actual FCM outcomes.

## Capabilities

### New Capabilities

- `customer-notification-inbox-campaign`: Rules for creating customer inbox rows from admin push campaigns independently of FCM success, and how that differs from admin `sent` counters.

### Modified Capabilities

- `push-firebase-delivery`: Platform-aware FCM multicast (native vs web), safe error handling, and no batch-level failure that silently abandons campaign completion.
- `push-campaign-storage`: Campaign dispatch MUST always reach a terminal `completed` or `failed` status; `total_sent` counts only FCM successes.
- `admin-push-notification-api`: Admin poll/list semantics must reflect terminal status and FCM-based counters after dispatch finishes or fails safely.
- `fcm-device-token-api`: Device token register/remove accept tokens up to 512 characters (web/PWA tokens).
- `fcm-device-token-storage`: `DeviceToken.token` storage length remains 512 with uniqueness preserved.

## Impact

- Backend: `notifications/services/fcm_service.py`, `notification_sender.py`, device token serializers/services, admin push views/tests, management command recovery path.
- Data: ensure `user_management.0025_device_token_length_512` is applied in production.
- Clients: Android app must keep receiving FCM; Flutter web on `app.befood.com.bd` must keep inbox + (when permission/token present) browser push. Flutter client changes outside this repo are verification-only unless a backend contract gap is found.
- Ops: ability to re-dispatch stuck campaigns; Firebase web push / VAPID configuration must be valid for web tokens.
- No intentional **BREAKING** API field removals; admin semantics for `sent` stay FCM-based (documented more clearly vs inbox).
