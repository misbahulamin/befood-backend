## 1. Model and migration

- [x] 1.1 Extend `RiderProfile` with `PublicIdMixin`/timestamps, phone, address, email-verification fields, approval status, `is_verified`/`verified_at`, rejection metadata, and admin notes (keep existing vehicle/availability fields)
- [x] 1.2 Create and apply migration with `public_id` backfill for any existing `RiderProfile` rows
- [x] 1.3 Register `RiderProfile` in Django admin with list/filter/search and approve/reject/`is_verified` sync mirroring service rules

## 2. Delivery Man auth services

- [x] 2.1 Implement `register_deliveryman` service (inactive user, profile, `DELIVERY_MAN` group, send verification email)
- [x] 2.2 Add Delivery Man email templates and send/verify helpers that update `RiderProfile` without touching customer verify paths
- [x] 2.3 Implement `approve_deliveryman` / `reject_deliveryman` / verified-status services (active flag sync + approval confirmation email; optional rejection email)
- [x] 2.4 Implement Delivery Man login response builder (token, user, groups, profile summary)

## 3. Delivery Man auth APIs

- [x] 3.1 Add serializers for register, login, resend verification, and `me`
- [x] 3.2 Add views for register, login, verify-email, resend-verification, and `me`
- [x] 3.3 Wire URLs under `user_management/deliveryman/...` and OpenAPI helpers for these endpoints
- [x] 3.4 Enforce login gates: invalid credentials, email unverified, pending/rejected approval message, success only when verified+active

## 4. Admin Delivery Man management APIs

- [x] 4.1 Add admin list/detail serializers with filters (approval status, email verified) and pending-queue default
- [x] 4.2 Add verified-admin views for list, detail, approve, reject, and verified-status update using `public_id`
- [x] 4.3 Wire URLs under `user_management/admin/deliverymen/...` with `is_verified_admin` permission checks and OpenAPI helpers

## 5. Tests

- [x] 5.1 Test registration success, duplicate email/phone validation, and verification email side effects
- [x] 5.2 Test email verify success/expiry/already-verified and that login stays blocked until approval
- [x] 5.3 Test pending-approval login message, rejected login block, and successful login after approve
- [x] 5.4 Test admin list pending filter, detail, approve, reject, revoke/re-approve, and non-admin permission denials

## 6. Documentation

- [x] 6.1 Write backend docs for Delivery Man auth + admin approval lifecycle (`user_management/docs/backend/`)
- [x] 6.2 Write frontend/integration docs with request/response examples for auth and admin management APIs (`user_management/docs/frontend/`)
- [x] 6.3 Run relevant test suite and fix regressions before marking the change complete
