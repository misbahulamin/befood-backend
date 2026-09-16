## Why

The backend already declares `firebase-admin` and `pyfcm` dependencies and has scaffolded notification models (`Notification`, `PushLog`, `NotificationPreference`), but there is no production-ready way for Flutter clients to register or deactivate FCM device tokens. Without a deduplicated, indexed token store and thin registration API, future push delivery cannot reliably target a user, multiple devices, or all active devices at scale.

## What Changes

- **Evolve existing `DeviceToken` model** in `user_management` (not a duplicate `UserDevice` table): add `device_name`, `app_version`, `last_used_at`, `updated_at`; enforce global unique `token`; add indexes for `(user, is_active)`, `token`, and `is_active`
- **Device token registration API**: `POST /notifications/device-token/` — authenticated users register or refresh FCM tokens; idempotent upsert with safe ownership transfer when the same physical device logs in as a different user
- **Device token removal API**: `POST /notifications/device-token/remove/` — soft-deactivate (`is_active=False`) the caller's token without deleting audit history
- **Service layer separation** in `notifications/services/`:
  - `device_service.py` — register, deactivate, query helpers (`get_user_device_tokens`, `get_all_active_device_tokens`)
  - `fcm_service.py` — stub/placeholder for future Firebase send integration (no credentials, no send logic in this change)
- **Mount notifications URLs** in `core/urls.py` (currently unmounted)
- **OpenAPI documentation** with `@extend_schema` and dedicated `notifications/api/openapi.py` examples
- **Backend + frontend docs** for Flutter integration workflow
- **Comprehensive tests**: auth, creation, refresh, ownership transfer, deactivation, query helpers, performance-safe querysets

## Capabilities

### New Capabilities

- `fcm-device-token-api`: Authenticated register and remove endpoints with validation, security, and documented response contracts
- `fcm-device-token-storage`: Evolved `DeviceToken` schema, indexes, migration, and data integrity rules (unique token, soft deactivation)
- `fcm-device-token-query`: Reusable read-only query services for active token lookup optimized for high-traffic send paths
- `fcm-device-token-frontend-docs`: Flutter integration guide covering register-on-login, refresh-on-token-change, remove-on-logout, and error handling

### Modified Capabilities

- (none — no existing OpenSpec capability covers device token management)

## Impact

- **Backend (`befood-backend`)**:
  - `user_management/models.py` — extend `DeviceToken`
  - `user_management/migrations/` — schema migration with indexes
  - `notifications/services/device_service.py` — new
  - `notifications/services/fcm_service.py` — stub only
  - `notifications/api/views.py`, `serializers.py`, `urls.py`, `openapi.py` — device token endpoints
  - `core/urls.py` — mount `/notifications/`
  - `notifications/tests/` — API and service tests
  - `notifications/docs/backend/`, `notifications/docs/frontend/` — integration docs
- **Reuse (no duplication)**:
  - Existing `DeviceToken` model and `user` FK (not a new table)
  - DRF Token auth (`Authorization: Token <key>`)
  - `IsAuthenticated` permission pattern
  - Thin APIView + service call pattern from `wallet/api/views.py`
  - `@extend_schema` OpenAPI pattern from `user_management/api/profile_views.py`
- **Out of scope**:
  - Firebase Admin SDK initialization or credential management
  - Actual FCM message sending
  - In-app notification inbox API hardening (existing scaffold)
  - JWT migration
  - Admin bulk token management UI
