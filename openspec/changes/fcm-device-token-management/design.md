## Context

### Current backend analysis (Phase 1 — completed)

**Apps structure**

| App | Relevance |
|-----|-----------|
| `user_management` | Owns `DeviceToken` model (minimal, unused in API) |
| `notifications` | Owns `Notification`, `PushLog`, `NotificationPreference`; API scaffold exists but URLs **not mounted** |
| `core` | Root URL routing, `PublicIdMixin`, settings |
| `permissions` | Shared `HasGroupPermission` |

**User model**

- Django default `auth.User` (no custom `AUTH_USER_MODEL`)
- Profile models: `CustomerProfile`, `RiderProfile`, `AdminProfile`, `StaffProfile` in `user_management/models.py`
- Device tokens link directly to `User`, not profile — correct for multi-role push

**Authentication**

- DRF **Token Authentication** (`rest_framework.authtoken`)
- Header: `Authorization: Token <key>`
- Login via `user_management/services/auth_service.py` → `get_login_response()`
- Logout deletes auth token in `user_management/api/views.py` — FCM token deactivation is a **separate explicit step**

**Existing `DeviceToken` model** (`user_management/models.py`)

```python
class DeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Gaps vs requirements**

| Requirement | Current state |
|-------------|---------------|
| Unique token | No unique constraint — duplicates possible |
| `last_used_at`, `updated_at` | Missing |
| `device_name`, `app_version` | Missing |
| Registration API | None |
| Deactivation API | None |
| Query services | None |
| FCM send | `firebase-admin` in requirements.txt, zero Python usage |
| URL mount | `notifications/api/urls.py` exists, not in `core/urls.py` |

**API patterns to reuse**

- Thin `APIView` + `@extend_schema` + service call (`wallet/api/views.py`, `user_management/api/profile_views.py`)
- Serializers validate shape; services own business logic (`django-drf-conventions.mdc`)
- Success envelope: `{"success": true, "message": "..."}` where established; validation errors via DRF serializer errors
- Tests: `APIClient` + `Token.objects.create` + `HTTP_AUTHORIZATION` (`user_management/tests/`)

**Database conventions**

- Default PK: `BigAutoField`
- Timestamps: `TimeStampedModel` in `user_management` (`created_at`, `updated_at`)
- Public resources use `public_id` UUID — **not applicable** to internal device tokens (never exposed in customer API)

### Decision: evolve `DeviceToken`, do not create `UserDevice`

A separate `UserDevice` model would duplicate the existing `DeviceToken` table and migration history. We extend `DeviceToken` in place with the missing fields and constraints. The user's `UserDevice` concept maps 1:1 to the evolved `DeviceToken`.

## Goals / Non-Goals

**Goals:**

- Production-ready token storage with unique constraint and optimized indexes
- Authenticated register/refresh and soft-remove endpoints at `/notifications/device-token/`
- Service-layer `register_device_token()` with atomic upsert and ownership transfer
- Query helpers returning only active, non-empty tokens via `values_list()` — no unnecessary User loads
- Clean separation: `device_service.py` (storage) vs `fcm_service.py` (future send)
- Full OpenAPI docs and Flutter integration guide
- Tests covering auth, idempotency, ownership transfer, deactivation, and query performance

**Non-Goals:**

- Firebase Admin SDK setup or sending push messages
- In-app notification inbox CRUD hardening
- Admin token management endpoints
- JWT auth migration
- Public UUID on device records

## Decisions

### 1. Model location: keep `DeviceToken` in `user_management`

**Why:** Model already exists with FK to `User` and migration history. Token lifecycle is tied to auth user identity.

**Alternative considered:** New model in `notifications` — rejected (duplicate table, split ownership).

### 2. API location: `notifications` app

**Why:** Device token endpoints are the entry point to the notification domain. Keeps `user_management` focused on auth/profiles. Matches user's requested URL prefix `/notifications/`.

**URL mount:** `path('notifications/', include('notifications.api.urls'))` in `core/urls.py`.

### 3. Permission: `IsAuthenticated` (not `HasCustomerProfile` only)

**Why:** Flutter apps may include customer and deliveryman clients. Any authenticated user should register their device. User is always resolved from `request.user` — never from request body.

### 4. Token uniqueness: global unique on `token` column

**Why:** FCM assigns one token per app installation. The same token cannot legitimately belong to two rows. Global unique enables fast lookup by token and prevents duplicate rows.

**Index:** `UniqueConstraint(fields=['token'], name='unique_device_token')` plus explicit `db_index=True` on `token` (redundant with unique but documents intent).

### 5. Composite index: `(user, is_active)`

**Why:** Primary send path query is `filter(user=user, is_active=True)`. Composite index covers this without a separate single-column `user` index when composite exists (PostgreSQL can use left-prefix; SQLite similar).

**Single `is_active` index:** Skip standalone — low selectivity alone; composite covers user-scoped queries. Token lookup uses unique index.

### 6. Ownership transfer when token exists for another user

**Behavior:** On register, if token row exists with a different `user`, **reassign `user` to the authenticated caller**, set `is_active=True`, update metadata and timestamps.

**Rationale:** Same physical device logged into a different account — the old user's push to that token would be wrong. FCM token is device-scoped, not user-scoped. Reassignment is the industry-standard approach (Firebase docs recommend updating token ownership on login).

**Security:** Only the holder of a valid auth token can trigger reassignment. Old user loses push to that device (expected on logout/device handoff).

**Alternative considered:** Reject with 409 — worse UX; stale tokens would block new user registration on shared devices.

### 7. Soft deactivation, not delete

**Behavior:** Remove endpoint sets `is_active=False`, updates `updated_at`. Row retained for audit correlation with future `PushLog`.

### 8. Register upsert logic (atomic)

```text
@transaction.atomic
register_device_token(user, token, platform, device_name=None, app_version=None):
  1. normalize: strip whitespace from token
  2. validate: non-empty, len 10–255, platform in allowlist
  3. get_or_create by token (with select_for_update on existing row)
  4. if exists:
       - if user != current: reassign user
       - set is_active=True, last_used_at=now, update optional fields
  5. if created:
       - set all fields, is_active=True, last_used_at=now
  6. return device record
```

Use `update_or_create` keyed on `token` as simpler alternative if select_for_update not needed — Django's `update_or_create` is sufficient for moderate traffic; wrap in `atomic()`.

### 9. Service file layout

```text
notifications/
  services/
    device_service.py    # register_device_token, deactivate_device_token, get_user_device_tokens, get_all_active_device_tokens
    fcm_service.py       # placeholder: send_to_user, send_to_tokens (raise NotImplementedError or pass)
  api/
    views.py             # DeviceTokenRegisterView, DeviceTokenRemoveView
    serializers.py
    urls.py
    openapi.py
```

### 10. Platform allowlist

`android`, `ios`, `web` — validated in serializer. Extensible via TextChoices on model.

### 11. Response contract

Register/remove success:

```json
{
  "success": true,
  "message": "Device registered successfully"
}
```

Remove success:

```json
{
  "success": true,
  "message": "Device deactivated successfully"
}
```

Validation errors: standard DRF 400 with field errors.

### 12. Field additions on `DeviceToken`

| Field | Type | Notes |
|-------|------|-------|
| `device_name` | CharField(100, blank=True) | Optional client label |
| `app_version` | CharField(50, blank=True) | Optional semver |
| `last_used_at` | DateTimeField(null=True) | Set on every register/refresh |
| `updated_at` | DateTimeField(auto_now=True) | Auto on save |

`platform` → use `TextChoices` with max_length 20 (unchanged).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Race condition on concurrent register for same token | `transaction.atomic()` + `update_or_create` keyed on unique `token` |
| Migration fails if duplicate tokens exist in DB | Data migration step: dedupe by keeping most recent `created_at` row, deactivate others before adding unique constraint |
| Token reassignment surprises old user | Expected behavior; document in frontend guide; old user should call remove on logout |
| `token` max_length 255 too short for future FCM formats | FCM tokens today ~140–200 chars; monitor; increase in additive migration if needed |
| High-frequency refresh writes | Upsert only updates when fields change; `last_used_at` always updated (acceptable write volume) |

## Migration Plan

1. **Data cleanup migration** (RunPython): Find duplicate `token` values; keep newest by `created_at`, delete or deactivate duplicates
2. **Schema migration**: Add new fields (`device_name`, `app_version`, `last_used_at`, `updated_at`); add `UniqueConstraint` on `token`; add composite index `(user, is_active)`
3. **Deploy code**: Services + API + URL mount
4. **Rollback**: Remove URL mount; revert migration if needed (no downstream send dependency yet)

## Open Questions

- (none blocking) — stakeholder confirmed Flutter-only clients for v1; `IsAuthenticated` covers all app roles
