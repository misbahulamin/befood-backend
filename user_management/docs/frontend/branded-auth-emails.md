# Branded auth emails & password reset (frontend)

## Summary

Registration / resend still use the existing verify flow. Password reset is requested via a new public endpoint; the email CTA opens the frontend reset page with `uid` and `token` query params.

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

Confirm-reset API (set new password) may be a follow-up; this change ships request + branded email only.

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
