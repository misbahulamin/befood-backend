# Customer password reset (frontend / mobile)

## Summary

Forgot-password is a complete public API flow: request email → open deep link **and/or** enter OTP → (optional) validate → confirm new password → **login again**. Confirm does **not** return an auth token.

OTP path (manual entry required; autofill optional): see [`../frontend-mobile/auth-verification-integration.md`](../frontend-mobile/auth-verification-integration.md). Note: `validate-otp` success alone must **not** unlock password change; `confirm-otp` must send the OTP again.

**Base:** `/user_management/`  
**Auth:** none on reset endpoints  
**Clients:** web + mobile  
**Optional header:** `X-Client-Type: web` | `mobile`

---

## End-to-end UI flow

1. User taps **Forgot password** and enters email.
2. Call **request** API. Always show a generic “check your email” screen (never say “email not found”).
3. User opens the email CTA. Deep link:

   `{FRONTEND_URL}/reset-password?uid=<uid>&token=<token>`

   Path may differ if backend `PASSWORD_RESET_FRONTEND_PATH` is customized.
4. Reset screen reads `uid` and `token` from the query (or deep-link extras on mobile).
5. On page load, call **validate**. If `400`, show “link invalid or expired” and offer to request again.
6. If valid, show new password + confirm fields. On submit, call **confirm**.
7. On confirm success, navigate to **login**. Do not expect a token in the confirm response.
8. User logs in with email + **new** password via existing `POST /user_management/login/`.

**Tip:** After reading `uid`/`token`, strip them from the browser URL (replaceState) so they are less likely to linger in history.

---

## 1. Request reset email

```http
POST /user_management/password-reset/
Content-Type: application/json

{
  "email": "customer@example.com"
}
```

**Success `200`:**

```json
{
  "message": "If an account exists for this email, password reset instructions will be sent."
}
```

Always treat as success for UX. Same message for unknown emails.

---

## 2. Validate link (recommended)

```http
POST /user_management/password-reset/validate/
Content-Type: application/json

{
  "uid": "<from query>",
  "token": "<from query>"
}
```

**Success `200`:**

```json
{
  "message": "Password reset link is valid."
}
```

**Error `400`:**

```json
{
  "detail": "Invalid or expired password reset link."
}
```

Use this before enabling the password form. Confirm remains the authoritative check.

---

## 3. Confirm new password

```http
POST /user_management/password-reset/confirm/
Content-Type: application/json

{
  "uid": "<from query>",
  "token": "<from query>",
  "new_password": "NewStrongPassword123",
  "confirm_password": "NewStrongPassword123"
}
```

**Success `200`:**

```json
{
  "message": "Password has been reset successfully. You can now login."
}
```

| Field | Notes |
|-------|--------|
| `uid` | From email link query param `uid` |
| `token` | From email link query param `token` |
| `new_password` | Min 8 chars; Django password validators apply |
| `confirm_password` | Must match `new_password` |

**Common errors `400`:**

- Passwords differ → `confirm_password` field error  
- Weak password → `new_password` field error(s)  
- Bad/expired/reused link → `{ "detail": "Invalid or expired password reset link." }`

---

## 4. Login after reset

```http
POST /user_management/login/
Content-Type: application/json

{
  "email": "customer@example.com",
  "password": "NewStrongPassword123"
}
```

- Old password will fail.
- If email is still unverified, login stays blocked (same as normal login). Prompt verify-email if needed.
- Any previous `Authorization: Token ...` for this user is invalid after confirm — clear local storage / secure store.

---

## Edge cases / UI states

| Situation | Suggested UI |
|-----------|----------------|
| Request always | “If an account exists, we sent instructions.” |
| Validate fails | Expired/invalid link + button to request again |
| Confirm reused link | Same as invalid link |
| Weak password | Show field errors from API |
| Confirm success | Toast + redirect to login (no auto-login) |
| Still unverified | After login failure, guide to resend verification |

---

## Headers

```http
Content-Type: application/json
X-Client-Type: web
```

No `Authorization` on request / validate / confirm.

---

## Related docs

- Full backend contract: `user_management/docs/backend/customer-password-reset.md`
- Branded email / deep-link settings: `user_management/docs/frontend/branded-auth-emails.md`
- Login / register: `docs/customer-auth-api.md`
