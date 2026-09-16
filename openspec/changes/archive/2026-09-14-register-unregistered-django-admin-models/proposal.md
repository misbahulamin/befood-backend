## Why

Recent FCM and push-notification work added and extended models such as `DeviceToken`, but several `user_management` models remain invisible in Django Admin. Operators cannot inspect device tokens, staff profiles, or user activity logs without raw database access, which slows support and debugging for push delivery and account issues.

## What Changes

- Register `DeviceToken` in `user_management/admin.py` with list display, filters, search, and read-only token metadata fields suitable for support workflows
- Register `StaffProfile` in `user_management/admin.py` with list display and user autocomplete
- Register `UserActivityLog` in `user_management/admin.py` as a read-only audit view (no add/change/delete)
- Follow existing admin patterns in the same file (`CustomerAuthOTPAdmin`, `RiderProfileAdmin`) for consistency
- No API, model, or migration changes — admin registration only

## Capabilities

### New Capabilities

- `django-admin-model-registration`: Django Admin registration for previously unregistered `user_management` models (`DeviceToken`, `StaffProfile`, `UserActivityLog`) with appropriate list views, filters, and permission posture

### Modified Capabilities

- (none — no existing OpenSpec capability requirement changes)

## Impact

- **Backend (`befood-backend`)**:
  - `user_management/admin.py` — three new `ModelAdmin` classes
  - No URL, serializer, service, or migration changes
- **Out of scope**:
  - Registering models in other apps (e.g. `business/`) unless discovered during implementation as directly related
  - Bulk admin actions on device tokens (deactivate, purge)
  - New API endpoints or permissions
