# FCM Device Token Management (Backend)

## Summary

Production-ready storage and API for Flutter clients to register and deactivate Firebase Cloud Messaging (FCM) device tokens. Token rows live in `user_management.models.DeviceToken`; registration APIs live under `/notifications/device-token/`. Firebase Admin SDK send logic is **not** included in this feature — see `notifications/services/fcm_service.py` for the future integration stub.

## Model: `DeviceToken`

Location: `user_management/models.py`

| Field | Type | Notes |
|-------|------|-------|
| `id` | BigAutoField | Internal PK |
| `user` | FK → `auth.User` | Owner; resolved from auth only |
| `token` | CharField(255), **unique** | FCM token string |
| `platform` | CharField | `android`, `ios`, or `web` |
| `device_name` | CharField(100), optional | Client label, e.g. "Pixel 8" |
| `app_version` | CharField(50), optional | App semver |
| `is_active` | Boolean | `False` after logout/remove |
| `last_used_at` | DateTime, nullable | Updated on every register/refresh |
| `created_at` | DateTime | Auto on create |
| `updated_at` | DateTime | Auto on save |

### Indexing

| Index | Purpose |
|-------|---------|
| Unique on `token` | Prevent duplicates; fast lookup by token during register |
| Composite `(user, is_active)` | Fast path: all active tokens for one user |

Standalone indexes on `user` or `is_active` alone are intentionally omitted — the composite index covers the primary per-user send query.

### Ownership transfer

When the same FCM token is registered by a different authenticated user, the existing row is **reassigned** to the new user. This matches physical device handoff (logout + login as another account on the same phone).

## Service layer

Location: `notifications/services/device_service.py`

| Function | Description |
|----------|-------------|
| `register_device_token(user, token, platform, ...)` | Atomic upsert; sets active, updates timestamps |
| `deactivate_device_token(user, token)` | Soft deactivate own token; returns `False` if not found or wrong user |
| `get_user_device_tokens(user)` | Active non-empty tokens for one user (`values_list`) |
| `get_all_active_device_tokens()` | All active non-empty tokens (`values_list`, no User prefetch) |

Future send code should call these helpers instead of querying `DeviceToken` directly.

## API endpoints

Base path: `/notifications/`

Auth header: `Authorization: Token <drf_token_key>`

### POST `/notifications/device-token/`

Register or refresh a device token.

**Request body**

```json
{
  "token": "fcm_token_from_flutter",
  "platform": "android",
  "device_name": "Pixel 8",
  "app_version": "1.2.0"
}
```

**Success (200)**

```json
{
  "success": true,
  "message": "Device registered successfully"
}
```

### POST `/notifications/device-token/remove/`

Soft-deactivate the caller's token (row retained for audit).

**Request body**

```json
{
  "token": "fcm_token_from_flutter"
}
```

**Success (200)**

```json
{
  "success": true,
  "message": "Device deactivated successfully"
}
```

**Not found (404)** — token missing or owned by another user.

## Migrations

1. `0015_deduplicate_device_tokens` — removes duplicate `token` rows (keeps newest by `created_at`)
2. `0016_extend_device_token` — adds fields, unique constraint, composite index

## Future FCM integration

Implement send in `notifications/services/fcm_service.py` after Firebase credentials are configured separately:

```python
from notifications.services.device_service import get_user_device_tokens
from notifications.services.fcm_service import send_to_user  # once implemented
```

Do not initialize Firebase in device token registration paths.

## Verification

```bash
python manage.py test notifications.tests.test_device_token
```

OpenAPI: `/api/docs/` → **Notifications** tag.
