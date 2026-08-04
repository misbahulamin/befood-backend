## Why

Befood already supports customer and admin authentication, but delivery partners have no registration, email verification, or admin-gated login path. Without a Delivery Man auth system, the upcoming delivery operations layer cannot onboard riders safely or keep unverified accounts out of the app.

## What Changes

- Extend the existing `RiderProfile` (Delivery Man profile) with registration identity fields (phone, address), email-verification state, and admin approval state (`is_verified` / approval timestamps / rejection reason).
- Add Delivery Man self-service auth APIs under `user_management`, aligned with customer/admin patterns:
  - registration
  - email verification (reuse shared token infrastructure)
  - resend verification
  - login (blocked until email verified **and** admin approved)
  - optional `me` endpoint for the authenticated delivery man
- Assign a Django group (e.g. `DELIVERY_MAN` / `RIDER`) on registration for role-based access.
- Add verified-admin APIs (and Django admin support) for Delivery Man management: pending list, detail, approve, reject, and verified-status control.
- Send confirmation email when an admin approves a Delivery Man account.
- Add tests and docs covering the full register → verify email → admin review → approve → login flow, plus blocked login for pending/rejected accounts.
- **Out of scope for this change:** delivery assignment/tracking UX, rider location streaming, vehicle document upload workflows beyond basic profile fields, mobile-only deep-link branding differences, and renaming the `delivery` ops app.

## Capabilities

### New Capabilities
- `deliveryman-auth`: Delivery Man registration, email verification, and login with dual gates (email verified + admin approved).
- `deliveryman-admin-management`: Verified-admin listing, detail, approve/reject, and verified-status management for Delivery Man accounts.

### Modified Capabilities
- (none)

## Impact

- **App:** `user_management/` (models/migrations, serializers, views, URLs, services, Django admin, email templates, tests, docs).
- **Auth patterns reused:** customer registration/email verification services; admin `is_verified` gate pattern from `AdminProfile` / `AdminLoginSerializer`.
- **Groups:** new `DELIVERY_MAN` (or `RIDER`) group via `get_or_create`, consistent with `CUSTOMER` / `ADMIN`.
- **Related (not redesigned now):** `delivery/` ops models (`RiderLocation`, `DeliveryAssignment`, etc.) remain separate; future delivery features can authorize via the new group/profile.
- **Clients:** Delivery Man mobile/web app gains register/login; Admin web panel gains a Delivery Man management section backed by new APIs (plus Django admin for ops fallback).
- **URLs:** Mounted under existing `user_management/` prefix (e.g. `/user_management/deliveryman/register/`, `/user_management/deliveryman/login/`) for consistency with customer/admin auth; public docs may alias the requested `/deliveryman/...` naming.
