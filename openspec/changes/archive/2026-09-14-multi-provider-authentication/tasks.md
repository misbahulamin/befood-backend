## 1. Baseline analysis and settings

- [x] 1.1 Confirm existing customer email deferred-registration, login, logout, OTP, and device-token paths still match design assumptions (no accidental breakage plan)
- [x] 1.2 Wire `GOOGLE_*`, `FACEBOOK_*`, and `SMS_NET_BD_*` into `core/settings/base.py` (and document keys in `.env.example`)
- [x] 1.3 Add phone-OTP related settings (reuse/extend `AUTH_OTP_*` pattern: TTL, max attempts, resend cooldown, max issues per hour)

## 2. Identity normalization helpers

- [x] 2.1 Implement `normalize_phone_number()` for BD mobiles (`017…` / `+880…` / `880…` → canonical `01XXXXXXXXX`) with validation errors for invalid input
- [x] 2.2 Implement `normalize_email()` as `lower().strip()` and apply on register/login/link/dedup paths
- [x] 2.3 Unit-test phone format variants and email case folding

## 3. Data model and migrations

- [x] 3.1 Add `CustomerProfile` phone verification fields (`is_phone_verified`, `phone_verified_at`) with safe defaults; keep `profile_completed` for phone-only onboarding
- [x] 3.2 Add `SocialIdentity` model: `user`, `provider` TextChoices (`google`, `facebook`, reserved `apple`), `provider_user_id`, unique `(provider, provider_user_id)`, timestamps
- [x] 3.3 Add phone OTP persistence model (hashed code, canonical phone key, expiry, attempts, issue window)—no plaintext OTP column
- [x] 3.4 Add per-device/session auth credential model (or equivalent) supporting current-session revoke vs revoke-all while keeping Token-header compatibility
- [x] 3.5 Generate and review additive Django migrations; migrate legacy single DRF Token rows safely; ensure existing users/profiles remain valid

## 4. Shared auth helpers

- [x] 4.1 Extract/reuse OTP hashing helpers consistent with email `CustomerAuthOTP`
- [x] 4.2 Add auth-session issue helper + **unified auth response builder** (`token`, `user`, `customer_profile`, `device_token_status`, shared additive fields)
- [x] 4.3 Add helper to upsert FCM `device_token` via `notifications.services.device_service` on auth success and set `device_token_status`
- [x] 4.4 Add customer user factory helpers for phone-only / social-only accounts (unique username, **`set_unusable_password()`**, `CUSTOMER` group, `CustomerProfile`, `profile_completed` handling)

## 5. Email auth hardening (preserve APIs)

- [x] 5.1 Apply email normalization on deferred register, verify, and login; still never create production `User` before verify
- [x] 5.2 Ensure email login still gates unverified/pending cases per existing contract
- [x] 5.3 Ensure email login uses unified response builder and optional `device_token` / `platform` upsert

## 6. SMS.NET.BD and phone OTP

- [x] 6.1 Implement `sms_net_bd` HTTP client (canonical→provider dial format in adapter only)
- [x] 6.2 Implement phone OTP issue service: normalize phone, rate limits, hash+store, send SMS, failure handling
- [x] 6.3 Implement phone OTP verify: attempt limits, expiry, consume code, create-or-login (password-less + phone-only profile rules), unified response
- [x] 6.4 Add serializers + views + URL routes for send OTP and verify OTP under `user_management`
- [x] 6.5 OpenAPI annotations for phone OTP endpoints

## 7. Social linking and OAuth providers

- [x] 7.1 Implement `social_linking` resolve-or-create with normalization: SocialIdentity → verified email → verified phone → create new (`set_unusable_password`)
- [x] 7.2 Implement Google credential verification against configured web/Android client IDs
- [x] 7.3 Implement Facebook token verification via Graph API (`FACEBOOK_GRAPH_VERSION`)
- [x] 7.4 Add Google and Facebook login serializers/views/URLs; unified response + device binding
- [x] 7.5 Conflict handling when provider id already bound to another user (`409`)
- [x] 7.6 OpenAPI annotations for OAuth endpoints

## 8. Session and logout

- [x] 8.1 Implement current-session logout (`/logout/`) — revoke only calling session; optional FCM deactivate for supplied `device_token`
- [x] 8.2 Implement logout-all (`/logout-all/`) — revoke all sessions; deactivate all FCM tokens for user
- [x] 8.3 Add admin force-logout service hook (all sessions + all FCM); document suspicious-login revoke hook for future
- [x] 8.4 Ensure password-reset path revokes all sessions when a usable password is reset
- [x] 8.5 Confirm `me` works for phone/social/email customers; document no idle auto-logout

## 9. Tests

- [x] 9.1 Regression: existing customer email register/verify/login/logout/password-reset/OTP tests still pass
- [x] 9.2 Regression: admin and deliveryman auth tests still pass
- [x] 9.3 Phone OTP: send, verify new user, verify existing user, wrong/expired OTP, cooldown, issue cap (mock SMS)
- [x] 9.4 Phone format variants: `017…` / `+880…` / `880…` resolve to same account/rate-limit key
- [x] 9.5 Email case normalization on register/login (`Test@` vs `test@`)
- [x] 9.6 Google/Facebook: new password-less user, returning user, invalid token, link by verified email
- [x] 9.7 Social conflict: Google id linked to user A cannot bind to user B
- [x] 9.8 Phone link with existing email user (shared verified phone / linking priority)
- [x] 9.9 Multi-device: device A and B both active (auth sessions + FCM)
- [x] 9.10 Logout current vs logout-all (sessions + FCM behavior)
- [x] 9.11 Unified auth response shape asserted across email/phone/google/facebook
- [x] 9.12 Session longevity without idle expiry; unauthorized access rejected

## 10. Documentation

- [x] 10.1 Backend docs under `user_management/docs/backend/` for multi-provider auth (normalization, phone-only profile, password-less, linking, unified response, logout policies, revoke events)
- [x] 10.2 Frontend/mobile integration notes (envelope fields, dual logout, device token)
- [x] 10.3 Update `.env.example` comments for required provider keys

## 11. Verification

- [x] 11.1 Run targeted `user_management` auth/device-related test modules and fix failures
- [x] 11.2 Manual smoke checklist: email deferred verify; phone OTP formats; Google/Facebook test tokens; multi-device logout current vs all; `me`
