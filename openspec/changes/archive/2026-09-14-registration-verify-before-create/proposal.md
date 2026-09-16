## Why

Wrong or unreachable emails currently leave permanent inactive `User` rows in the database because signup creates the account before verification succeeds. Push delivery is also unreliable when customers register on the web and later log in on mobile, because device-token association is easy to miss outside a dedicated post-login sync. Together these create incomplete accounts and missed notifications.

## What Changes

- **Defer permanent customer account creation until email verification succeeds.** Signup stores registration intent temporarily and sends OTP/link; only a successful verify creates the active `User` + `CustomerProfile`.
- **Stop accumulating unverified customer users** from failed or abandoned signups (wrong email, never completed OTP).
- **Update auth email subjects** so the OTP/code appears at the start of the subject for email verification and password-reset emails. Email body HTML/text layout and styling stay unchanged.
- **Unify device-token upsert behavior** so mobile register/login paths reliably create or update the caller's FCM token via the existing device-token service (no duplicate token rows for the same token value).
- **Client contract updates** for web (`befood-frontend`) and mobile (`befood_mobile`): registration still returns “check your email”, but verify becomes the account-creation moment; login remains the primary device-token sync trigger (with hardening as needed).
- Password-reset request/confirm flows remain intact aside from subject formatting; purpose-isolated OTP rules stay.

## Capabilities

### New Capabilities

- `deferred-customer-registration`: Signup no longer permanently creates a customer `User` until email OTP/link verification succeeds; pending signup data is temporary, rate-limited, and cleaned up.
- `auth-otp-email-subject`: Auth emails that carry an OTP put the code first in the subject line while keeping existing body templates/design.
- `device-token-auth-sync`: Ensure FCM device tokens are upserted for the authenticated customer on mobile auth success (login, and register-then-login), reusing existing storage/API rules.

### Modified Capabilities

- *(none in `openspec/specs/` — prior auth/OTP/device-token work lives only under completed change folders and was never synced to main specs)*

## Impact

- **Backend (`befood-backend`)**
  - `user_management/services/auth_service.py` — registration no longer calls `User.save()` before verify
  - `user_management/services/email_verification.py`, `auth_otp.py`, models — pending registration + OTP issuance without a permanent user
  - Verify endpoints (`verify-email` link + OTP) — create and activate account on success
  - Resend verification — operate against pending registration, not inactive users
  - Unverified-login auto-resend path — adapt to “no permanent unverified user” world
  - Email subject templates: `customer_activation_subject.txt`, `customer_password_reset_subject.txt`
  - `notifications/services/device_service.py` + login/device-token call sites — harden upsert / document auth-time sync
  - Tests + backend/frontend integration docs under `user_management/docs/` and `notifications/docs/`
- **Mobile (`befood_mobile`)** — verify UX stays; account exists only after OTP; ensure `syncTokenIfNeeded` after every successful login (including first login after web signup)
- **Frontend (`befood-frontend`)** — modal register → OTP flow unchanged for users; no web device-token registration required
- **Out of scope:** deliveryman registration/approval, admin auth, email body layout/CSS changes, password-reset business logic beyond subject text
