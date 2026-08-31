# Customer auth OTP (backend)

## Quick summary

Customers can verify email and reset passwords using **either**:

1. A 6-digit **OTP** from a branded email, or
2. The existing **deep link** (`uid` + `token`)

Both channels are sent in the same email when a new OTP is issued. Link APIs are unchanged.

| Area | Endpoints |
|------|-----------|
| Verify email (link) | `GET /user_management/verify-email/<uidb64>/<token>/` |
| Verify email (OTP) | `POST /user_management/verify-email/otp/` |
| Resend verification | `POST /user_management/resend-verification/` |
| Resend (OTP alias) | `POST /user_management/verify-email/resend-otp/` |
| Password reset request | `POST /user_management/password-reset/` |
| Request OTP alias | `POST /user_management/password-reset/request-otp/` |
| Reset validate (link) | `POST /user_management/password-reset/validate/` |
| Reset confirm (link) | `POST /user_management/password-reset/confirm/` |
| Reset validate OTP | `POST /user_management/password-reset/validate-otp/` |
| Reset confirm OTP | `POST /user_management/password-reset/confirm-otp/` |

All OTP/auth recovery endpoints above are **public** (`AllowAny`).

## Model: `CustomerAuthOTP`

| Field | Meaning |
|-------|---------|
| `user` | Django user |
| `purpose` | `email_verification` or `password_reset` (never interchangeable) |
| `code_hash` | **HMAC-SHA256** digest of the 6-digit code |
| `created_at` | Issue time (cooldown + hourly counting) |
| `expires_at` | Absolute expiry |
| `consumed_at` | Set when successfully used; null while active |
| `attempt_count` / `max_attempts` | Failed verify attempts |

**Critical:** The database stores **`code_hash` only**. Plaintext values such as `123456` are **never** persisted. Plaintext exists only in memory while composing the outbound email.

## Settings

| Setting | Default | Role |
|---------|---------|------|
| `AUTH_OTP_TTL_SECONDS` | `600` (10 min) | OTP lifetime |
| `AUTH_OTP_MAX_ATTEMPTS` | `5` | Failed checks before lockout for that row |
| `AUTH_OTP_RESEND_COOLDOWN_SECONDS` | `60` | Min interval before a **new** OTP/email |
| `AUTH_OTP_MAX_ISSUES_PER_HOUR` | `10` | Max new OTP rows per user+purpose per rolling hour |

## Security rules

1. Purpose isolation — verification OTP cannot reset password and vice versa.
2. Hash-only storage + constant-time compare.
3. Single use (`consumed_at`).
4. Expiry + attempt limits.
5. Resend cooldown: if an **active** OTP exists and was created within cooldown → **reuse** (no new email).
6. Hourly issue cap after cooldown elapses.
7. Password reset: `validate-otp` does **not** consume and does **not** grant reset authority. `confirm-otp` **always re-verifies** independently.
8. Successful password reset (link or OTP) deletes all DRF `Token` rows for that user.
9. Anti-enumeration on request/resend for unknown emails.

## Issue / send flow

Service: `user_management/services/auth_otp.py` + callers in `email_verification.py` / `password_reset.py`.

1. Try `issue_otp(user, purpose)`.
2. Status `issued` → invalidate prior actives, store hash, send branded email with `otp_code` + link.
3. Status `reused` → no new row, **no email**.
4. Status `rate_limited` → no new row, **no email** (public APIs still return generic success where required).

## Email verification OTP

### `POST /user_management/verify-email/otp/`

```json
{ "email": "customer@example.com", "otp": "123456" }
```

Success:

```json
{ "message": "Email verified successfully. You can now login." }
```

Errors (`400`): `{ "detail": "Invalid or expired OTP." }` or `{ "detail": "OTP expired." }`

### Resend

Same behavior for `resend-verification` and `verify-email/resend-otp`. Cooldown may skip sending; response message stays client-friendly / anti-enumeration.

## Password reset OTP

### Request

`POST /user_management/password-reset/` or `.../request-otp/`

```json
{ "email": "customer@example.com" }
```

Always:

```json
{ "message": "If an account exists for this email, password reset instructions will be sent." }
```

### Validate OTP (UX only)

`POST /user_management/password-reset/validate-otp/`

```json
{ "email": "customer@example.com", "otp": "123456" }
```

Success does **not** authorize password change. Client must still submit OTP on confirm.

### Confirm OTP (authoritative)

`POST /user_management/password-reset/confirm-otp/`

```json
{
  "email": "customer@example.com",
  "otp": "123456",
  "new_password": "StrongPassword123",
  "confirm_password": "StrongPassword123"
}
```

Backend independently verifies OTP again, consumes it, sets password, deletes DRF tokens.

## Unverified login auto delivery

Correct password + unverified → `400` with:

```json
{
  "detail": "Your account is not verified yet. Please check your email for the verification code or link.",
  "code": "email_not_verified"
}
```

Triggers verification delivery with **cooldown reuse** (no spam on repeated logins within 60s). Wrong password → `Invalid credentials` and **no** email.

## How to verify

- Migration: `user_management.0013_customer_auth_otp`
- Tests: `user_management/tests/test_customer_auth_otp.py` (+ existing link auth / password-reset tests)

## Related docs

- Frontend/mobile: `user_management/docs/frontend-mobile/auth-verification-integration.md`
- Link password reset: `user_management/docs/backend/customer-password-reset.md`
- Overview: `docs/customer-auth-api.md`
