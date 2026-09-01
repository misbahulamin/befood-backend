## 1. Model and migration

- [x] 1.1 Extend `DeviceToken` in `user_management/models.py`: add `device_name`, `app_version`, `last_used_at`, `updated_at`; add `Platform` TextChoices; add `Meta.indexes` composite `(user, is_active)` and `UniqueConstraint` on `token`
- [x] 1.2 Create data migration to deduplicate existing `token` rows (keep newest by `created_at`) before unique constraint
- [x] 1.3 Create schema migration for new fields, unique constraint, and composite index
- [x] 1.4 Run migrations locally and verify no integrity errors

## 2. Service layer

- [x] 2.1 Create `notifications/services/device_service.py` with `register_device_token()` — normalize, validate, atomic upsert, ownership transfer, timestamp updates
- [x] 2.2 Add `deactivate_device_token(user, token)` — soft deactivate own token only
- [x] 2.3 Add `get_user_device_tokens(user)` — active non-empty tokens via `values_list("token", flat=True)`
- [x] 2.4 Add `get_all_active_device_tokens()` — broadcast query via `values_list`, no User prefetch
- [x] 2.5 Create `notifications/services/fcm_service.py` stub with documented placeholder send functions (no Firebase init)

## 3. API layer

- [x] 3.1 Create serializers: `DeviceTokenRegisterSerializer`, `DeviceTokenRemoveSerializer` with platform allowlist and length validation
- [x] 3.2 Create `DeviceTokenRegisterView` (POST) and `DeviceTokenRemoveView` (POST) with `IsAuthenticated`, thin service calls, success envelope responses
- [x] 3.3 Wire URLs in `notifications/api/urls.py`: `device-token/`, `device-token/remove/`
- [x] 3.4 Mount `notifications/` in `core/urls.py`
- [x] 3.5 Add `notifications/api/openapi.py` with request/response examples; apply `@extend_schema` on both views

## 4. Tests

- [x] 4.1 Test: unauthenticated register → 401
- [x] 4.2 Test: authenticated register creates new device row
- [x] 4.3 Test: same user re-register does not duplicate, updates `last_used_at`, sets active
- [x] 4.4 Test: token exists for different user → ownership transferred to current user
- [x] 4.5 Test: invalid platform / empty token / oversized fields → 400
- [x] 4.6 Test: remove own token → `is_active=False`, row not deleted
- [x] 4.7 Test: remove another user's token → 404 without modification
- [x] 4.8 Test: remove already inactive token → 200 idempotent
- [x] 4.9 Test: `get_user_device_tokens` returns only active non-empty tokens
- [x] 4.10 Test: `get_all_active_device_tokens` excludes inactive and uses values_list (assert query count)
- [x] 4.11 Test: OpenAPI schema generation includes device token endpoints

## 5. Documentation

- [x] 5.1 Write `notifications/docs/backend/fcm-device-token.md` — model, indexes, services, API, migration, future FCM integration
- [x] 5.2 Write `notifications/docs/frontend/fcm-device-token.md` — Flutter register-on-login, refresh-on-change, remove-on-logout, headers, examples, errors

## 6. Verification

- [x] 6.1 Run `python manage.py test notifications.tests.test_device_token` (or equivalent test module)
- [x] 6.2 Verify `/api/docs/` shows Notifications tag with both endpoints
- [x] 6.3 Confirm no Firebase credentials required at startup
