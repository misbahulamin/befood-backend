## Why

Customers can request a branded password-reset email today (`POST /user_management/password-reset/`), but there is no backend API to validate the reset token or set a new password. Frontend and mobile apps cannot finish the recovery flow. Completing confirm + session invalidation and shipping clear client docs unblocks production forgot-password UX.

## What Changes

- Extend `user_management` password-reset services with **token validation** and **confirm / set-new-password** (reuse existing `PasswordResetTokenGenerator` + uidb64; do not invent a second token system).
- Add public API endpoints under `/user_management/` for validate (optional but recommended for SPA UX) and confirm, alongside the existing request endpoint.
- On successful password change: apply Django password validators, save the new password, and **invalidate existing DRF auth tokens** so stolen sessions cannot survive a reset.
- Keep anti-enumeration on the request endpoint; return precise validation errors on confirm for invalid/expired uid+token and weak passwords.
- Add/update OpenAPI annotations for the new endpoints.
- Write detailed backend + frontend/mobile API documentation so clients can integrate without reading backend code.
- Update existing branded-auth-emails docs that currently say confirm API is a follow-up.
- Automated tests for success, invalid/expired token, weak password, non-customer users, and post-reset token invalidation.

## Capabilities

### New Capabilities
- `customer-password-reset`: Complete customer password recovery contract — request (existing), validate token, confirm new password, security rules (token isolation from activation, DRF token wipe, anti-enumeration).
- `customer-password-reset-api-docs`: Client-facing and backend technical documentation covering full workflow, endpoints, payloads, errors, and integration steps for web + mobile.

### Modified Capabilities
- (none — request/email behavior already shipped via prior email-template work; not yet archived into `openspec/specs/`. This change owns the remaining confirm/docs requirements as new capabilities.)

## Impact

- **Code:** `user_management/services/password_reset.py`, `api/serializers.py`, `api/views.py`, `api/urls.py`, OpenAPI helpers if present, tests under `user_management/tests/`.
- **APIs:** Existing `POST /user_management/password-reset/` unchanged in contract; new public validate + confirm routes (proposed: `POST .../password-reset/validate/` and `POST .../password-reset/confirm/`).
- **Auth:** DRF `Token` rows deleted for the user after successful reset; clients must re-login.
- **Docs:** `user_management/docs/backend/`, `user_management/docs/frontend/`, and cross-links from `docs/customer-auth-api.md` / branded-auth-emails docs.
- **Out of scope:** Admin and deliveryman forgot-password flows; JWT migration; changing email templates beyond what’s needed for confirm docs.
