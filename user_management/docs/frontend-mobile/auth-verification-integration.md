# Auth verification integration (React + Android)

## Summary

BeFood supports **OTP + link** for:

- Email verification after registration
- Password reset

OTP always supports **manual entry**. Platform autofill (SMS/email suggestion APIs) is **optional** — never rely on autofill alone.

Public APIs need no `Authorization` header.

| Header | Value |
|--------|--------|
| `Content-Type` | `application/json` |
| `X-Client-Type` | optional `web` or `mobile` (same OTP contract) |

Base path: `/user_management/`

---

## React: registration → verify → login

1. `POST /customer/register/` with `{ email, password }`
2. Show OTP screen (6 digits, **manual input**) and/or “open email link”
3. Either:
   - `POST /verify-email/otp/` with `{ email, otp }`, or
   - Handle SPA route `/verify-email?...` / path segments and call existing link verify `GET /verify-email/<uidb64>/<token>/`
4. `POST /login/` with email + password

### Resend OTP

- `POST /resend-verification/` or `POST /verify-email/resend-otp/`
- Body: `{ "email": "..." }`
- Enforce **60s cooldown** in UI (disable resend button). Backend also enforces cooldown — may not send a second email within the window.

### Unverified login

If user tries login before verifying:

```json
{
  "detail": "Your account is not verified yet. Please check your email for the verification code or link.",
  "code": "email_not_verified"
}
```

Show verification UI. Backend may have just (re)sent email, or reused an active OTP within cooldown (no new mail).

Wrong password still returns `Invalid credentials` (no `email_not_verified` code).

---

## React: password reset (OTP)

1. `POST /password-reset/` or `POST /password-reset/request-otp/` with `{ email }`
2. Always show success toast (anti-enumeration) — do not say whether the account exists
3. Optional UX: `POST /password-reset/validate-otp/` with `{ email, otp }`
   - **Do not** unlock password change based only on this response
   - Keep OTP in component state / ask user again
4. `POST /password-reset/confirm-otp/` with `{ email, otp, new_password, confirm_password }`
   - Server **re-verifies** OTP independently
5. `POST /login/` with the new password

### Password reset (link)

Deep link example: `https://befood.com.bd/reset-password?uid=<uid>&token=<token>`

Then existing:

- `POST /password-reset/validate/` `{ uid, token }`
- `POST /password-reset/confirm/` `{ uid, token, new_password, confirm_password }`

---

## Android

### OTP screen

- Always provide a manual 6-digit field
- Optional: Autofill / SMS User Consent / email OTP parsers if available
- Never require autofill to complete the flow

### Deep links

Handle:

- Verification: frontend verification path with `uid` / `token` (see branded email / `FRONTEND_URL`)
- Reset: `/reset-password?uid=...&token=...`

Call the same public APIs as web.

### Password reset OTP

Same as React: `request-otp` → (optional) `validate-otp` → **`confirm-otp` must include `otp` again**.

---

## API cheat sheet

### Verify email OTP

`POST /user_management/verify-email/otp/`

```json
{ "email": "customer@example.com", "otp": "123456" }
```

Success: `{ "message": "Email verified successfully. You can now login." }`  
Error: `{ "detail": "Invalid or expired OTP." }`

### Confirm password with OTP

`POST /user_management/password-reset/confirm-otp/`

```json
{
  "email": "customer@example.com",
  "otp": "123456",
  "new_password": "StrongPassword123",
  "confirm_password": "StrongPassword123"
}
```

Success: `{ "message": "Password reset successfully." }`

---

## UX rules (must follow)

1. Manual OTP entry always available
2. Autofill is optional platform behavior
3. Resend button respects ~60s cooldown
4. `validate-otp` success ≠ permission to change password
5. After reset/verify, call **login** (no auto token from confirm/verify)

## Backend reference

`user_management/docs/backend/email-verification-otp.md`
