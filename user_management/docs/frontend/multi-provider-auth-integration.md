# Multi-Provider Auth — Frontend / Mobile Integration

## Base path

`/user_management/`

Auth header after login: `Authorization: Token <token>`

## Unified login / register UX

```text
Pick method
  ├─ Email → POST /customer/email-check/
  │     exists    → password → POST /login/
  │     pending   → resume verify OTP/link
  │     available → password → POST /customer/register/ → verify
  ├─ Google / Facebook → POST /oauth/google|facebook/
  └─ Phone → POST /phone/otp/send/ → POST /phone/otp/verify/
```

After any success envelope (or after email verify), if `phone_verification_required === true`:

```text
POST /phone/otp/bind/send/   (Authorization: Token …)
POST /phone/otp/bind/verify/
```

Do **not** use anonymous `/phone/otp/verify/` for a logged-in social/email user needing a phone — that can create a second account. Use **bind** endpoints.

Existing users without phone: login still succeeds; show a non-blocking phone prompt from the flag.

## Endpoints

### Email-first check

`POST /customer/email-check/` `{ "email": "user@example.com" }`

```json
{ "email": "user@example.com", "status": "exists" | "pending" | "available" }
```

### Email (existing)

1. `POST /customer/register/` `{ email, password }` → pending (no User yet)
2. Verify via OTP or link → includes `phone_verification_required` + existing `message`
3. `POST /login/` `{ email, password, device_token?, platform? }`

### Phone OTP (anonymous create-or-login)

1. `POST /phone/otp/send/` `{ "phone": "01712345678" }`  
   Also accept `+8801712345678` / `8801712345678`.
2. `POST /phone/otp/verify/` `{ "phone", "otp", "device_token?", "platform?" }`  
   → unified envelope; creates phone-only account if new.

Cooldown limits: `429` with `code` `OTP_COOLDOWN` or `OTP_RATE_LIMITED`.

### Authenticated phone bind

Requires `Authorization: Token <token>`.

1. `POST /phone/otp/bind/send/` `{ "phone" }`
2. `POST /phone/otp/bind/verify/` `{ "phone", "otp", "device_token?", "platform?" }`

`409` + `code: PHONE_CONFLICT` if phone belongs to another customer.

### Google

`POST /oauth/google/` `{ "id_token": "<Google ID token>", "device_token?", "platform?" }`

### Facebook

`POST /oauth/facebook/` `{ "access_token": "<FB user token>", "device_token?", "platform?" }`

### Logout

| Endpoint | Behavior |
|----------|----------|
| `POST /logout/` | Current device/session only. Body optional: `{ "device_token" }` to deactivate that FCM token. |
| `POST /logout-all/` | All sessions + all FCM tokens for the user. |

### Me

`GET /me/` — requires valid token. Includes `phone_verification_required`. Tokens do **not** idle-expire.

## Unified success envelope (all methods)

Required top-level keys:

- `token`
- `user`
- `customer_profile`
- `device_token_status` — `{ "status": "bound" | "omitted" | "failed", ... }`
- `auth_provider` — `email` | `phone` | `google` | `facebook`
- `phone_verification_required` — boolean
- `verification_status` — see below
- `groups`
- `onboarding_completion`
- `location_confirmation`

### `verification_status`

```json
{
  "email_verified": false,
  "phone_verified": true,
  "google_verified": false,
  "facebook_verified": false,
  "identity_verified": true
}
```

Use **`identity_verified`** to decide whether the customer may use gated features (orders, subscriptions, wallet). Do **not** require `email_verified` for phone / Google / Facebook users.

Phone-only / social users may have blank `user.email`. Prefer `phone_verification_required` over inferring from onboarding alone.

Onboarding treats phone as complete only when verified (`is_phone_verified`).

## Feature access (identity gate)

Authenticated customer APIs that previously required email verification now require **any** verified identity (`identity_verified`).

| English API detail (example) | Suggested Bangla UI |
|------------------------------|---------------------|
| `Identity verification is required before placing an order.` | আপনার অ্যাকাউন্ট যাচাই সম্পন্ন হয়নি। দয়া করে একটি যাচাইকৃত মাধ্যম দিয়ে অ্যাকাউন্ট নিশ্চিত করুন। |

Email verification UI / resend remains only for the **email** ownership flow — not as a universal block after phone or social login.

Guest service-area / location checks stay public and are **not** blocked by identity verification.

## Device token tips

- Pass `device_token` + `platform` (`android`|`ios`|`web`) on any auth success path to upsert FCM.
- Soft-fail: login still succeeds if FCM upsert fails; inspect `device_token_status`.
- Multiple devices stay active until logout-all or per-token deactivate.
- On current logout, send the same FCM token you registered if you want push stopped on that device only.

## Backward compatibility

- Additive fields only; ignore unknown fields safely on older clients.
- Deploy does **not** invalidate existing tokens or force logout.
- Email verify still returns the original `message` string plus new fields.
- Email verification remains for ownership / recovery / messaging; feature access uses `identity_verified`.

## Errors

- `400` — validation / invalid OTP / invalid OAuth token
- `401` — missing/revoked token on protected routes
- `409` — social provider id already linked (`SOCIAL_CONFLICT`) or phone owned elsewhere (`PHONE_CONFLICT`)
- `429` — phone OTP cooldown / hourly cap
