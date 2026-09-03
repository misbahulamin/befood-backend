# Deferred customer registration (verify before account create)

## Quick summary

Customer signup **does not** create a permanent Django `User` until email verification succeeds. Registration upserts a temporary `PendingCustomerRegistration` row, sends OTP + link email, and only then creates an active verified customer account.

| Step | What happens |
|------|----------------|
| `POST /user_management/customer/register/` | Upsert pending row; send verification email; **no** `User` |
| `POST /user_management/verify-email/otp/` | Create active `User` + verified `CustomerProfile`; delete pending |
| `GET /user_management/verify-email/<uidb64>/<token>/` | Same finalize for pending-scoped links (legacy inactive users still work) |
| `POST /user_management/resend-verification/` | Resend for pending (or legacy unverified user) |
| `POST /user_management/login/` | Works only after verify; pending-only emails → invalid credentials |

## Model: `PendingCustomerRegistration`

| Field | Meaning |
|-------|---------|
| `email` | Unique normalized email |
| `password_hash` | Django password hash (copied onto User at finalize) |
| `first_name` / `last_name` / `phone` / `occupation` / `is_bachelor` | Optional signup fields |
| `otp_*` | Hashed OTP, expiry, attempts, hourly issue window |
| `expires_at` | Pending row lifetime (default 24h); cleanup deletes expired rows |

## Email subjects (OTP first)

Body HTML/text templates are **unchanged**. Subjects only:

- Activation: `{{ otp_code }} is your sign-in verification code`
- Password reset: `{{ otp_code }} is your password reset code`

## Ops commands

```bash
# Delete expired pending signups (safe hourly cron)
python manage.py cleanup_pending_registrations

# Preview / convert legacy inactive unverified Users → pending
python manage.py migrate_unverified_customers_to_pending --dry-run
python manage.py migrate_unverified_customers_to_pending
```

After legacy migrate, those emails must re-verify (resend or re-register) before login.

## Login + optional device token

```json
POST /user_management/login/
{
  "email": "user@example.com",
  "password": "...",
  "device_token": "<fcm-token>",
  "platform": "android"
}
```

`device_token` + `platform` are optional. When present, login calls the same upsert as `POST /notifications/device-token/`. Mobile clients should still call the dedicated device-token API after login if they omit these fields.

## Permissions

Register / verify / resend remain public. Device-token upsert on login uses the newly authenticated user.

## How to verify

1. Register → confirm no `auth_user` row; pending exists; email subject starts with 6 digits.
2. Wrong OTP → still no user.
3. Correct OTP → user active + verified; pending gone; login works.
4. `cleanup_pending_registrations` removes expired pending only.
