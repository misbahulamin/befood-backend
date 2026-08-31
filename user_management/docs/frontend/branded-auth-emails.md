# Branded auth emails & password reset (frontend)

## Summary

Registration / resend still use the existing verify flow (now **OTP + link** in the same email). Password reset is requested via a public endpoint; the email includes a CTA deep link **and** a 6-digit OTP. The SPA/app can use link validate/confirm and/or OTP validate/confirm, then logs the user in again.

Full client guide (link): [`customer-password-reset.md`](./customer-password-reset.md).  
OTP + dual-channel guide: [`../frontend-mobile/auth-verification-integration.md`](../frontend-mobile/auth-verification-integration.md).

## Integration

### Password reset request

```http
POST /user_management/password-reset/
Content-Type: application/json

{ "email": "customer@example.com" }
```

Success (`200`):

```json
{
  "message": "If an account exists for this email, password reset instructions will be sent."
}
```

Always show a generic “check your email” UI — do not reveal whether the account exists.

### Reset page deep link

Email button opens:

`{FRONTEND_URL}/reset-password?uid=<uidb64>&token=<token>`

Path is configurable via backend `PASSWORD_RESET_FRONTEND_PATH` (default `/reset-password`).

### Complete reset on the client

1. Read `uid` and `token` from the query / deep link.
2. `POST /user_management/password-reset/validate/` with `{ "uid", "token" }` (recommended before showing the form).
3. `POST /user_management/password-reset/confirm/` with `{ "uid", "token", "new_password", "confirm_password" }`.
4. Navigate to login — confirm does **not** return an auth token.
5. `POST /user_management/login/` with email + new password.

Details, errors, and edge cases: [`customer-password-reset.md`](./customer-password-reset.md).

### Activation (frontend deep link)

- Register / resend → branded “Verify Email Address” email
- Email CTA opens the **website** SPA route (never the API host):

`{FRONTEND_URL}/verify-email/<uidb64>/<token>/`

Path is configurable via `EMAIL_VERIFICATION_FRONTEND_PATH` (default `/verify-email`).
`FRONTEND_URL` must be the public site origin (e.g. `https://befood.com.bd`), not `https://api.befood.com.bd`.

- SPA page then calls `GET /user_management/verify-email/<uidb64>/<token>/`
- No OTP code UI in the email

## Headers

Public endpoints — no `Authorization` required. Optional `X-Client-Type: web|mobile`.

## Target clients

Mobile + web.
