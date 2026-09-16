## Why

Customers today can only create and sign in with email + password (deferred registration + email OTP/link). Environment credentials for Google, Facebook, and SMS.NET.BD already exist, but the backend does not consume them. Mobile and web clients need a production-ready multi-provider auth foundation—email, phone OTP, Google, and Facebook—on one shared User/CustomerProfile system, with long-lived sessions until the user explicitly logs out, without breaking existing customer, admin, or deliveryman flows.

## What Changes

- Keep and harden the existing customer **email + password** deferred-registration path (no production User until email is verified).
- Add **centralized identity normalization**: `normalize_phone_number()` for BD formats (`017…` / `+880…` / `880…` → one canonical form) and `normalize_email()` (`lower().strip()`) on all register/login/link/search paths.
- Add **phone number + OTP** registration/login using SMS.NET.BD (hashed OTP storage, expiry, attempt limits, resend cooldown, rate limits, SMS failure handling).
- Phone-only accounts: only verified phone is mandatory at creation; name/email via later profile completion; maintain `profile_completed` state; use `set_unusable_password()`.
- Add **Google OAuth** and **Facebook OAuth** backend verification and customer create-or-login; new social/phone-only users use `set_unusable_password()`.
- Add **SocialIdentity** with `provider` TextChoices (`google`, `facebook`, future-ready `apple`) and **account linking** by verified email then verified phone.
- **Unified auth success response** across email, phone, Google, and Facebook: `token`, `user`, `customer_profile`, `device_token_status`, plus shared additive fields.
- **Session policy:** long-lived auth until logout or security revoke. Default customer logout = **current session/device**; separate **logout-all**; document revoke events (password reset, admin force logout, suspicious login hooks).
- Ensure **multiple active FCM device tokens**; clarify FCM behavior on current-device vs logout-all.
- Wire unused `.env` keys (`GOOGLE_*`, `FACEBOOK_*`, `SMS_NET_BD_*`) into settings and services.
- Add/extend backend tests (including phone format variants, email case, social conflict, multi-device, phone-link-to-email-user, logout current vs all); do **not** remove or break existing customer/admin/deliveryman auth APIs.
- No **BREAKING** removal of current email auth endpoints; additive APIs preferred. Existing login response gains documented shared fields for unification (compatible additive shape).

## Capabilities

### New Capabilities

- `customer-email-auth`: Customer email registration, email verification (OTP/link), email normalization, login gating on verified accounts, and compatibility with deferred `PendingCustomerRegistration`.
- `phone-otp-auth`: Phone normalization, OTP issue/verify via SMS.NET.BD, create-or-login (including phone-only minimal profiles), rate limits, and secure OTP persistence.
- `google-oauth-login`: Backend verification of Google ID tokens/credentials and customer create-or-login with password-less new accounts.
- `facebook-oauth-login`: Backend verification of Facebook access tokens via Graph API and customer create-or-login with password-less new accounts.
- `social-account-linking`: Link provider identities (enum providers) to existing customers by normalized verified email then normalized verified phone; prevent duplicate accounts and unsafe conflicts.
- `auth-session-management`: Long-lived sessions; unified auth response; current-device logout vs logout-all; security revoke event documentation/hooks (no forced idle expiry).
- `auth-device-binding`: After successful customer auth, upsert/maintain FCM `DeviceToken` for multiple devices; align FCM deactivate behavior with logout current vs logout-all.

### Modified Capabilities

<!-- No existing openspec capability encodes customer multi-provider auth. Deliveryman/admin auth requirements are unchanged. -->

## Impact

- **Apps:** `user_management` (models, services, API views/serializers/urls, tests, docs); `notifications` device-token integration points; `core/settings` for Google/Facebook/SMS config.
- **Existing preserved:** Customer deferred email register/verify/login/password-reset; admin login; deliveryman register/verify/login; `HasCustomerProfile` / group permissions; Token-based API auth (extended for per-session revoke as designed).
- **New/extended data:** `SocialIdentity` with provider choices, phone verification state, phone OTP records (hashed), per-device/session auth records if required for current-device logout, thin `CustomerProfile` extensions—prefer additive tables over breaking `auth.User`.
- **External systems:** Google token verification APIs; Facebook Graph API; SMS.NET.BD send/report/balance endpoints.
- **Dependencies:** May use Google auth libraries already adjacent in requirements; SMS HTTP client; no mandatory switch to SimpleJWT.
- **Clients:** Frontend/mobile integrate against one auth response shape and dual logout endpoints after this foundation.
