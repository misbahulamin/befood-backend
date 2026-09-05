## Context

Customer auth today lives in `user_management`:

- Standard Django `User` (no custom `AUTH_USER_MODEL`) + `CustomerProfile` (phone optional, `is_email_verified`, existing `profile_completed`).
- Email signup uses **deferred registration** (`PendingCustomerRegistration`): no production User until email OTP/link verification succeeds.
- Login issues a non-expiring **DRF Auth Token** (historically one row per user); logout deletes that user’s token row(s).
- Email OTP reuse patterns already exist (`CustomerAuthOTP`, `AUTH_OTP_*` settings, HMAC-hashed codes).
- FCM `DeviceToken` upsert exists via `/notifications/device-token/` and optionally on login; multiple FCM rows per user are already supported.
- Admin and deliveryman auth are separate personas and must remain untouched.
- `.env` already has `GOOGLE_*`, `FACEBOOK_*`, `SMS_NET_BD_*` placeholders; settings/code do not wire them yet. `djangorestframework-simplejwt` is in requirements but unused.

Stakeholders: customer web/mobile (primary), notification delivery, future FE/mobile integration. Admin/deliveryman consumers must see no regression.

## Goals / Non-Goals

**Goals:**

- One customer identity can authenticate via email+password, phone+OTP, Google, or Facebook.
- Centralize **phone** and **email** normalization so format/case variants never create duplicate identities.
- Unverified email registrations must not become production Users (preserve deferred registration).
- Phone OTP via SMS.NET.BD with hashed storage, TTL, attempts, resend cooldown, hourly issue caps, and clear SMS failure errors.
- Phone-only signup: verified phone mandatory only; name/email later via profile completion; keep `profile_completed` accurate.
- Password-less Google/Facebook/phone-only accounts use `set_unusable_password()`.
- Backend-only verification of Google/Facebook credentials; never trust client-claimed profile fields alone.
- Link social logins by **normalized verified email first**, then **normalized verified phone**.
- **Unified auth success response** for every customer auth method.
- Long-lived sessions with **current-device logout** (default) and **logout-all**; document security revoke events (password reset, admin force logout, suspicious login).
- Multiple active FCM device tokens; logout policies must state FCM side effects clearly.
- Additive APIs under existing `user_management/` mount; keep current email/admin/deliveryman endpoints working.

**Non-Goals:**

- Replacing Django `User` with a custom user model in this change.
- Migrating the whole API to JWT/SimpleJWT (unless a later change revisits it).
- Implementing Apple Sign-In in this change (enum value reserved only).
- Full suspicious-login detection product (hooks/docs only in this change).
- Social login for admin or deliveryman personas.
- Building frontend/mobile UI (backend foundation only).
- Full interactive account-merge UI for conflicting identities.

## Decisions

### 1. Auth sessions support current-device vs logout-all

**Decision:** Keep Token-header compatibility for clients (`Authorization: Token <key>`), but introduce **per-device/session auth credentials** so default logout can revoke only the calling session while other devices stay signed in. Provide:

- `POST .../logout/` — revoke **current** auth credential (+ optional FCM `device_token` deactivate for that device when supplied).
- `POST .../logout-all/` — revoke **all** auth credentials for the user (+ deactivate all FCM device tokens for that user, or document equivalent bulk policy).

Documented **security revoke events** (implement or stub hooks as practical in this change):

| Event | Effect |
|-------|--------|
| Manual current logout | Revoke current session only |
| Manual logout-all | Revoke all sessions |
| Password reset (when password is set) | Revoke all sessions |
| Admin force logout | Revoke all sessions (admin API or service hook) |
| Suspicious login (future) | Hook/interface reserved; may revoke all or challenge |

No idle/auto logout.

**Why:** Product requires mobile “log out this phone” without signing out every device, plus ops/security “kill all sessions.”

**Alternatives considered:** Keep single DRF `Token` per user (current logout = always all devices) — rejected against final logout policy. Full JWT access/refresh — rejected for this change (client migration).

**Implementation note:** Prefer an additive `AuthSession` (or equivalent) keyed opaque token with `user`, optional `device_token`/`platform`/`user_agent`, `created_at`, `revoked_at`, while still presenting the key in the familiar `Token` header scheme (custom auth class or carefully extended token model). Existing email login clients must keep working: first login after deploy still returns a usable key; document migration of legacy single-token rows.

### 2. Do not introduce a custom User model

**Decision:** Keep `django.contrib.auth.models.User`. Extend identity via `CustomerProfile` + `SocialIdentity`.

**Profile additions (additive):**

- `is_phone_verified` / `phone_verified_at`.
- Continue using existing `profile_completed` / `profile_completion_percentage` for phone-only and social incomplete profiles.
- Username strategy for phone-only / social-only: unique generated usernames; **always** `set_unusable_password()` when no password is chosen.
- Email may be blank until later profile/link; serializers must tolerate missing email.

### 3. SocialIdentity with provider TextChoices

**Decision:** Model fields:

- `user` FK
- `provider` — `TextChoices`: `google`, `facebook`, `apple` (**reserved**; Apple login not implemented in this change)
- `provider_user_id`
- unique `(provider, provider_user_id)`
- optional `email_at_link` (normalized), timestamps; minimize raw secret storage

**Why:** Enum keeps providers explicit and Apple-ready without a new table later.

### 4. Centralized phone and email normalization

**Decision:**

```text
normalize_phone_number(raw) -> canonical BD local 10-digit starting with 01
  accepts: 01712345678 | +8801712345678 | 8801712345678 | optional spaces/dashes
  rejects: non-BD / invalid length after normalize

normalize_email(raw) -> lower().strip()
```

Canonical phone storage on `CustomerProfile.phone` and phone OTP keys MUST use the normalized form. All OTP send/verify, social linking, customer search/dedup, and register/login email comparisons MUST call these helpers—no ad-hoc formatting in views.

**SMS.NET.BD:** Convert canonical → provider dial string in the SMS client adapter only (keep domain storage canonical).

**Why:** Prevents duplicate accounts from format/case variants.

**Open question resolved:** Canonical storage = existing 10-digit local `01XXXXXXXXX`; SMS adapter owns provider-specific formatting.

### 5. Phone OTP model separate from email OTP

**Decision:** Phone OTP rows keyed by **normalized phone**, hash-only code, TTL/attempts/issue window. Flows:

1. Send OTP → normalize → rate-limit → hash+store → SMS.NET.BD.
2. Verify → on match existing profile phone → login; else create password-less customer with `is_phone_verified=True`, empty/partial profile, `profile_completed=False` until completion rules say otherwise → login.
3. Success response uses **unified auth envelope**.

### 6. Phone-only profile rules

**Decision:** At phone OTP account creation, **only verified phone is mandatory**. Name, email, and other profile fields are optional and completed later via existing customer profile APIs. System MUST keep `profile_completed` (and percentage helper if present) consistent so clients can prompt onboarding.

### 7. Social login verify-then-link

**Google:** Prefer ID token; verify audience against `GOOGLE_WEB_CLIENT_ID` / `GOOGLE_ANDROID_CLIENT_ID`.

**Facebook:** Access token + Graph API with `FACEBOOK_APP_ID` / `SECRET` / `GRAPH_VERSION`.

**Linking priority (after normalize):**

1. Existing `SocialIdentity` for provider+id → login.
2. Provider verified email matches customer with `is_email_verified=True` (normalized email) → link + login.
3. Verified phone match on `is_phone_verified` (normalized) → link + login.
4. Else create new customer + `SocialIdentity` with `set_unusable_password()`.

**Conflict:** Provider id already bound to another user → `409`, no takeover.

### 8. Password-less accounts

**Decision:** Any new User created via Google, Facebook, or phone OTP MUST call `set_unusable_password()`. Email+password path keeps usable hashed passwords. Password-reset applies only when a usable password exists or after an explicit set-password flow (out of band if needed).

### 9. Unified auth success response

**Decision:** Shared builder for email login, phone verify, Google, Facebook:

```json
{
  "token": "<auth-session-key>",
  "user": { },
  "customer_profile": { },
  "device_token_status": { },
  "auth_provider": "email|phone|google|facebook",
  "groups": [ ]
}
```

Exact nested field names align with existing login serializer where possible; additive fields documented. `device_token_status` reports whether an upsert ran (`bound` / `unchanged` / `omitted` / `failed` soft-fail policy—prefer soft-fail FCM upsert without failing auth).

### 10. Settings wiring

Load via `config()` in `core/settings/base.py`: Google, Facebook, SMS.NET.BD keys as in proposal. Fail closed when provider endpoints are called without credentials.

### 11. API surface (additive under `user_management/`)

| Area | Method | Path (illustrative) |
|------|--------|---------------------|
| Phone send OTP | POST | `/user_management/phone/otp/send/` |
| Phone verify | POST | `/user_management/phone/otp/verify/` |
| Google | POST | `/user_management/oauth/google/` |
| Facebook | POST | `/user_management/oauth/facebook/` |
| Logout current | POST | `/user_management/logout/` |
| Logout all | POST | `/user_management/logout-all/` |
| Existing | — | register, verify-email, login, me |

### 12. Device token binding and logout FCM policy

**Decision:** Shared upsert helper on all auth successes when `device_token` present. Multiple active FCM tokens per user required.

| Auth action | Auth sessions | FCM DeviceToken |
|-------------|---------------|-----------------|
| Login (any method) with device_token | Create/refresh current session | Upsert that token active for user |
| Logout current (+ optional device_token) | Revoke current session only | Deactivate that FCM token if provided; else leave FCM as-is |
| Logout-all | Revoke all sessions | Deactivate all FCM tokens for user |
| Admin force logout | Revoke all sessions | Deactivate all FCM tokens for user |

### 13. Service layer layout

Under `user_management/services/`:

- `phone_normalization.py` / `email_normalization.py` (or single `identity_normalization.py`)
- `sms_net_bd.py`, `phone_otp.py`
- `google_oauth.py`, `facebook_oauth.py`, `social_linking.py`
- `auth_session.py` — issue/revoke current/all, unified response builder
- Reuse OTP hashing helpers from email OTP

### 14. Security controls

- Hash OTPs; never log OTP/OAuth secrets/Authorization headers.
- Rate-limit phone OTP by normalized phone + IP.
- Normalize before uniqueness checks.
- Password hashing for email accounts only when usable password is set.

## Risks / Trade-offs

- **[Risk] Migrating from single DRF Token to per-session keys** → Mitigation: additive auth class + migration of existing Token rows into sessions; regression tests for email login header.
- **[Risk] Phone-only users lack email** → Mitigation: blank email allowed; profile completion + serializers tolerate null/blank email.
- **[Risk] Account takeover via unverified social email** → Mitigation: link only on provider-verified email + local `is_email_verified`.
- **[Risk] SMS downtime** → Mitigation: stable error codes; careful issue-budget handling.
- **[Risk] Breaking FE assumptions** → Mitigation: additive endpoints; unified envelope remains backward-compatible with existing token+user fields; dual logout documented.

## Migration Plan

1. Settings + normalization helpers + model migrations (`SocialIdentity`, phone verification, phone OTP, auth sessions if new).
2. Ship phone OTP + SMS client (tests mock HTTP).
3. Ship Google/Facebook + linking.
4. Unified response + device binding on all success paths.
5. Logout current + logout-all + document revoke hooks; admin force-logout service entry point.
6. Deploy additive migrations; migrate legacy tokens carefully.
7. Rollback: disable new routes; reverse migrations only if no critical production rows.

## Open Questions

- Exact Google credential type from mobile vs web (default: **ID token**).
- Whether phone OTP send returns generic success to reduce enumeration (product preference).
- Soft-fail vs hard-fail when FCM upsert throws on login (default: **soft-fail**, auth still succeeds, `device_token_status` reflects failure).
