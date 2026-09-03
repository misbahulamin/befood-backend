## Context

Customer signup today (`register_customer` in `user_management/services/auth_service.py`) immediately creates a Django `User` (`is_active=False`) and `CustomerProfile` (`is_email_verified=False`), then sends a branded activation email with a 6-digit OTP (`CustomerAuthOTP`, purpose `email_verification`) plus a uid/token link. Wrong emails therefore leave permanent inactive rows. Password reset already reuses the same OTP subsystem with purpose `password_reset` and must keep working. FCM tokens live on `DeviceToken` and are upserted only via authenticated `POST /notifications/device-token/` (`register_device_token`); login/register do not touch tokens. Mobile syncs after login; web never registers tokens.

Constraints: keep email HTML/text body design unchanged; keep public OTP/link API shapes usable by `befood-frontend` and `befood_mobile`; do not break deliveryman auth; OpenSpec/implementation home is this backend repo with client follow-ups documented.

## Goals / Non-Goals

**Goals:**

- No permanent customer `User` until email verification succeeds.
- Temporary signup storage with OTP + link verification, cooldown/rate limits, and cleanup of abandoned attempts.
- OTP visible at the start of activation and password-reset email subjects.
- Reliable device-token create/update for mobile users after auth (web signup → later mobile login included).
- Preserve password-reset confirm behavior and anti-enumeration messaging.

**Non-Goals:**

- Changing email body layout, CSS, or branding chrome.
- Deliveryman registration / approval flows.
- Requiring web browsers to register FCM device tokens.
- Collapsing multi-device support into a hard single-token-per-user policy (upsert remains token-keyed; multiple active devices stay allowed).
- Rewriting progressive profile onboarding after first login.

## Decisions

### 1. Pending registration model instead of inactive `User`

**Choice:** Introduce `PendingCustomerRegistration` (name may vary) holding normalized email, password hash, optional progressive signup fields, timestamps, expiry, and verification secrets. `POST .../customer/register/` upserts this row and sends the activation email. Successful OTP or link verify atomically creates `User` + `CustomerProfile` (active + verified), then deletes/consumes the pending row.

**Alternatives considered:**

- Keep creating inactive users and purge later → still pollutes `auth_user`, breaks “no permanent account”, and confuses admin customer lists.
- Redis-only pending store → harder to reason about in Django admin/tests and couples auth to cache availability.
- Create user only for OTP FK convenience → contradicts the product requirement.

**Rationale:** Matches the stated product rule, keeps relational integrity for signup data, and lets us expire/clean abandoned attempts without touching real accounts.

### 2. Verification secrets without a real `User`

**Choice:**

- **OTP:** Issue and verify email-verification OTPs against the pending registration (hashed HMAC, TTL, attempts, cooldown, hourly cap — same numeric settings as today). Password-reset OTP continues to use `CustomerAuthOTP` bound to real users only.
- **Link:** Replace user-pk-based `EmailVerificationTokenGenerator` for the *pending* path with a pending-scoped signed token (e.g. Django `TimestampSigner` or stored random token hash on the pending row). Keep the public URL shape `GET /user_management/verify-email/<uidb64>/<token>/` by encoding the pending id (with a clear discriminator if needed so legacy inactive users can still verify during migration).

**Alternatives considered:**

- Force OTP-only and drop links → breaks existing web/mobile deep links and emails.
- Null `CustomerAuthOTP.user` FK → mixes pending and real-user OTP rows and complicates password-reset isolation.

**Rationale:** Dual-channel UX stays; purpose isolation stays; password-reset architecture stays user-bound.

### 3. Register / resend / login contract compatibility

**Choice:**

- Register response stays success-oriented `{ message, email }` without auth token.
- If email already belongs to an **active verified** customer → reject as today (email taken).
- If a **pending** row exists for the email → update password/fields as allowed, re-issue OTP subject to cooldown (do not create a second pending identity).
- Resend endpoints operate on pending registrations; unknown/expired emails keep anti-enumeration style responses.
- Login against a non-existent user (never verified) returns generic invalid credentials. Legacy inactive unverified users (pre-migration) keep a compatibility path: either one-time migrate to pending, verify-in-place, or purge after notice.

**Rationale:** Clients already expect register → OTP screen → login; only the server-side persistence timing changes.

### 4. Email subject-only OTP presentation

**Choice:** Update subject templates only:

- Activation: `{{ otp_code }} is your sign-in verification code`
- Password reset: `{{ otp_code }} is your password reset code` (same “code first” rule)

Pass `otp_code` into subject render context (already available when sending). Do not alter HTML/text body templates.

**Rationale:** Inbox preview shows the code without opening the mail; body design work from prior branded-email changes is preserved.

### 5. Device token sync remains dedicated API; harden auth-time client duty

**Choice:** Keep `register_device_token` upsert-by-token semantics (`update_or_create` on unique `token`, reassign user on handoff). Do not create tokens inside unauthenticated register. Require authenticated mobile clients to call `POST /notifications/device-token/` after every successful login (already implemented — verify/fix gaps). Optionally accept `device_token` + `platform` on login as a convenience that calls the same service inside the login transaction/response path so web→mobile first login cannot “forget” sync.

**Alternatives considered:**

- Create token during register → register is unauthenticated and often pre-verify; no stable user yet under the new model.
- One row per user enforced uniquely → breaks multi-device and existing schema.

**Rationale:** Fixes the real gap (ensure upsert after mobile auth) without breaking multi-device or the notifications module boundary.

### 6. Cleanup & ops

**Choice:** Pending rows carry `expires_at` (aligned with OTP/link lifetime or slightly longer). Add a management command (and optional cron hook documentation) to delete expired pending registrations. Document manual cleanup of legacy inactive unverified customers.

## Risks / Trade-offs

- [Link token redesign] → Clients keep the same path pattern; add regression tests for OTP and link; dual-read legacy inactive users during migration window.
- [Abandoned pending + email squatting] → Pending expires; re-register allowed after expiry; cooldown prevents spam; verified users still own the email permanently.
- [Race: verify vs second register] → Use `transaction.atomic()` + row locks on pending email; create user only once; unique email on `User` remains the final guard.
- [Subject line leaks OTP to lock-screen notifications] → Accepted product trade-off; TTL/attempt limits unchanged.
- [Login optional device_token is a small API additive] → Backward compatible; clients that omit the field rely on existing post-login sync.
- [Legacy inactive users in production] → Migration plan required so old signups are not stranded.

## Migration Plan

1. Ship `PendingCustomerRegistration` + dual verify path behind the same public URLs.
2. New registers write pending only.
3. Backfill strategy for existing `User` with `customer_profile.is_email_verified=False` and `is_active=False`: prefer convert-to-pending (copy password hash + email) or allow verify-in-place until a cutoff, then purge.
4. Deploy subject template updates with the same release (no client change required).
5. Confirm mobile post-login device-token sync in staging (web register → mobile login).
6. Rollback: feature flag or revert register/verify services to prior inactive-user creation if critical; subject templates are independently reversible.

## Open Questions

- Exact subject copy for password reset (`password reset code` vs `sign-in verification code`) — defaulting to purpose-specific wording with code-first format unless product dictates identical phrase for both.
- Whether login body should gain optional `device_token`/`platform` in this change or remain docs-only mobile sync enforcement — prefer optional login fields for reliability.
- Retention window for pending rows beyond OTP TTL (proposal default: pending expires with last issued verification secret, max 24h to match link lifetime).
