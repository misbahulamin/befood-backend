# Multi-Provider Customer Authentication

## Quick summary

Customers can authenticate with:

| Method | Endpoints |
|--------|-----------|
| Email-first check | `POST /user_management/customer/email-check/` |
| Email + password (deferred registration) | `POST /user_management/customer/register/`, verify, `POST /user_management/login/` |
| Phone OTP (SMS.NET.BD) | `POST /user_management/phone/otp/send/`, `POST /user_management/phone/otp/verify/` |
| Authenticated phone bind | `POST /user_management/phone/otp/bind/send/`, `POST /user_management/phone/otp/bind/verify/` |
| Google | `POST /user_management/oauth/google/` |
| Facebook | `POST /user_management/oauth/facebook/` |

All auth success paths return the **same unified envelope**. Sessions are long-lived until logout (no idle expiry).

**Phone gate (soft):** `phone_verification_required` is `true` when `CustomerProfile.is_phone_verified` is false. Tokens are still issued; clients run phone OTP / bind UX. Existing users are never force-logged-out.

**Identity gate (hard, authenticated customers only):** Customer feature access (orders, subscriptions, wallet endpoints using `IsVerifiedCustomer`, etc.) requires `identity_verified` — any one of email verified, phone verified, Google `SocialIdentity`, or Facebook `SocialIdentity`. Guest/anonymous service-area flows are **not** subject to this gate. Email verification remains for ownership, recovery, and messaging; it is **not** the sole access requirement.

Google may set `is_email_verified` only when the ID token asserts `email_verified=true`. Facebook email presence alone does **not** set `is_email_verified` (provider identity ≠ email ownership).

## Unified auth response

```json
{
  "token": "<opaque AuthSession key>",
  "user": { "id": 1, "email": "", "first_name": "", "last_name": "" },
  "groups": ["CUSTOMER"],
  "customer_profile": {
    "phone": "+8801712345678",
    "occupation": null,
    "is_bachelor": null,
    "is_email_verified": false,
    "is_phone_verified": true,
    "profile_completed": false,
    "profile_completion_percentage": 0
  },
  "device_token_status": { "status": "bound|omitted|failed" },
  "auth_provider": "email|phone|google|facebook",
  "phone_verification_required": false,
  "verification_status": {
    "email_verified": false,
    "phone_verified": true,
    "google_verified": false,
    "facebook_verified": false,
    "identity_verified": true
  },
  "onboarding_completion": {},
  "location_confirmation": {}
}
```

`verification_status.google_verified` / `facebook_verified` are derived from `SocialIdentity` rows (no denormalized booleans). `identity_verified` is the OR of all provider flags.

Header for authenticated calls: `Authorization: Token <token>`.

`GET /me/` and customer profile reads also expose `phone_verification_required`.

## Email-first check

`POST /user_management/customer/email-check/` `{ "email": "..." }`

| status | Meaning | Client next |
|--------|---------|-------------|
| `exists` | Verified production customer | Password login |
| `pending` | Active deferred registration | Resume verify / register |
| `available` | Neither | Collect password → register |

No token is issued. Email is normalized (`lower().strip()`).

## Email verification response (additive)

After OTP/link verify succeeds:

```json
{
  "message": "Email verified successfully. You can now login.",
  "email_verified": true,
  "phone_verification_required": true
}
```

Existing `message` remains for backward compatibility. Login still required after verify (no auto-token).

## Authenticated phone bind

For social/email users who already have a session but need a verified phone:

1. `POST /phone/otp/bind/send/` `{ "phone": "017…" }` (auth required)
2. `POST /phone/otp/bind/verify/` `{ "phone", "otp", "device_token?", "platform?" }`

Attaches phone to the **current** profile (`is_phone_verified=True`). Does **not** create a second User.

Conflict when phone belongs to another customer → `409` with `code: PHONE_CONFLICT`.

Anonymous `phone/otp/verify/` create-or-login remains unchanged for phone-first users.

## Identity normalization

- `normalize_email()` → `lower().strip()` on all register/login/link/check paths.
- `normalize_phone_number()` → canonical **10-digit** BD national form (`1712345678`).
  Accepts `017…`, `+880…`, `880…`, and spaced/dashed variants.
- SMS adapter converts canonical → `880…` dial string only at send time.

## Phone-only accounts

- Only verified phone is required at creation.
- `set_unusable_password()`; name/email completed later via profile APIs.
- Onboarding treats `phone` as complete only when `is_phone_verified=True`.

## Password-less social accounts

Google/Facebook new users also use `set_unusable_password()`. New social users without verified phone get `phone_verification_required: true` (token still issued). A linked `SocialIdentity` alone makes `identity_verified: true` so orders/subscriptions are allowed without email verification.

## Social linking priority

1. Existing `SocialIdentity` (provider + provider_user_id)
2. Provider verified email ↔ local `is_email_verified` (Google `email_verified` claim only; Facebook email presence is not treated as verified ownership)
3. Verified phone ↔ local `is_phone_verified`
4. Else create new customer + bind identity

Conflict (provider id owned by another user) → HTTP `409`.

Provider enum: `google`, `facebook`, reserved `apple` (not implemented). Helper `is_customer_identity_verified` is the extension point for future providers.

## Session / logout policy

| Action | Auth sessions | FCM DeviceToken |
|--------|---------------|-----------------|
| Login (+ optional device_token) | New `AuthSession` | Soft-fail upsert |
| `POST /logout/` | Revoke **current** session | Deactivate supplied `device_token` if any |
| `POST /logout-all/` | Revoke **all** | Deactivate all for user |
| Password reset (usable password) | Revoke all | (sessions only; FCM unchanged unless force-logout) |
| Admin `force_logout_user(user)` | Revoke all | Deactivate all |

`suspicious_login_revoke_hook` aliases `force_logout_user` for future detection.

No idle auto-logout.

## Backward compatibility

- Additive response fields only (`phone_verification_required`, `verification_status`, email-verify extras).
- Existing AuthSession / legacy Token keys are **not** invalidated by this change.
- Existing email login, register, phone OTP, Google/Facebook endpoints remain.
- Customers with `is_email_verified=True` remain `identity_verified`.
- Admin / deliveryman auth unchanged. Guest service-area checks unchanged.

## Models

- `CustomerProfile.is_phone_verified` / `phone_verified_at`
- `SocialIdentity`
- `PhoneAuthOTP` (hashed code only)
- `AuthSession` (per-device Token-compatible key)

Legacy DRF `Token` rows are migrated into `AuthSession`. Admin/deliveryman may still issue classic Tokens; authentication checks AuthSession first, then Token.

## Settings / env

See `.env.example`: `GOOGLE_*`, `FACEBOOK_*`, `SMS_NET_BD_*`, optional `PHONE_OTP_*`.

## How to verify

```bash
python manage.py test user_management.tests.test_identity_normalization user_management.tests.test_identity_verification user_management.tests.test_multi_provider_auth user_management.tests.test_customer_auth user_management.tests.test_unified_customer_auth_flow orders.tests.test_orders orders.tests.test_customer_subscription
```

## Manual smoke checklist

1. Email-check → register → OTP verify (`phone_verification_required`) → login → bind phone OTP
2. Google new → flag true → bind send/verify → flag false; same User id
3. Legacy email login without phone → `200` + token + flag true
4. Phone OTP anonymous create-or-login still works
5. Login on two devices → logout current on A → B still works → logout-all

## Credential linking & phone availability (additive)

### Email-check credential flags

`POST /user_management/customer/email-check/` — when `status` is verified `exists` only:

```json
{
  "email": "user@gmail.com",
  "status": "exists",
  "has_password": false,
  "password_setup_required": true
}
```

`available` / `pending` responses do **not** include credential flags.

### Login code

`POST /user_management/login/` — unusable-password account → HTTP 400 with `code: "password_setup_required"`.

### Set password

`POST /user_management/set-password/` (authenticated):

- Body: `{ "password", "password_confirm", "current_password?" }`
- Unusable password → `current_password` not required
- Usable password → `current_password` required (`CURRENT_PASSWORD_REQUIRED`)
- Auth success envelope and `GET /me/` expose `has_password`

### Phone availability

`POST /user_management/phone/check-availability/`

Body: `{ "phone": "01XXXXXXXXX", "context": "bind" | "login" }`

- `login`: existing phones remain allowed (OTP login). Never sends SMS.
- `bind`: phone owned by another customer → `available: false`, `reason: "PHONE_ALREADY_REGISTERED"` (auth required).
- If `context` omitted: authenticated → bind, else → login.

### Bind send guard

`POST /user_management/phone/otp/bind/send/` re-checks ownership **before SMS**. Conflict → HTTP 409 `PHONE_CONFLICT` (no SMS).
