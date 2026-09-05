## 1. Identity verification helper

- [x] 1.1 Add `user_management/services/identity_verification.py` with `is_customer_identity_verified(user)` (email OR phone OR Google SocialIdentity OR Facebook SocialIdentity), structured for future provider OR branches
- [x] 1.2 Add helpers to build `verification_status` dict (`email_verified`, `phone_verified`, `google_verified`, `facebook_verified`, `identity_verified`) from a user/profile
- [x] 1.3 Add unit tests covering email-only, phone-only, Google-only, Facebook-only, and fully unverified customers

## 2. Auth response contract and null-safe phone users

- [x] 2.1 Extend `build_customer_auth_response` to include `verification_status` while keeping existing `customer_profile.is_email_verified` / `is_phone_verified`
- [x] 2.2 Confirm phone OTP, Google OAuth, Facebook OAuth, and email login paths all use the shared builder (fix any path that bypasses it)
- [x] 2.3 Audit auth/response builders for unsafe email ops (e.g. `user.email.lower()` without null/empty guard); harden phone-only null/empty email paths
- [x] 2.4 Update multi-provider auth tests to assert `verification_status` and a phone-only null-email auth response success case

## 3. Replace customer feature gates (authenticated only)

- [x] 3.1 Update `orders.api.permissions.IsVerifiedCustomer` to use `is_customer_identity_verified` and English message `Identity verification is required before placing an order.` (or equivalent)
- [x] 3.2 Update order serializers that block on email verification to use the unified helper + identity error copy
- [x] 3.3 Update subscription serializers that block on email verification to use the unified helper + identity error copy
- [x] 3.4 Repo-wide search for customer access gates using `is_email_verified`, `email_verified`, `Email verification is required`, and `verified customer`; replace authenticated customer access checks with the helper; leave email-ownership, admin, deliveryman, and email-verify flows unchanged
- [x] 3.5 Confirm guest/anonymous checkout and location flows are not newly blocked by identity verification

## 4. Provider flag persistence and social vs email ownership

- [x] 4.1 Verify phone OTP success always persists `is_phone_verified=True` (+ timestamp); fix gaps if found
- [x] 4.2 Verify Google/Facebook OAuth success always persists `SocialIdentity`; fix gaps if found
- [x] 4.3 Audit social linking/OAuth so `is_email_verified` is set only when policy trusts a provider-asserted verified email (not merely email present or social login success); tighten Facebook/Google paths if needed
- [x] 4.4 Confirm email verification OTP/link and pending registration finalize still set `is_email_verified=True` and remain available

## 5. Tests and regression

- [x] 5.1 Add/adjust order tests: phone-verified + email unverified can place order; email-only unverified still blocked; email-verified still allowed
- [x] 5.2 Add/adjust subscription tests for phone/Google/Facebook identity-verified customers (`is_email_verified=False`)
- [x] 5.3 Assert gate errors use identity-oriented English (not “Email verification is required…”)
- [x] 5.4 Smoke-check guest/anonymous supported flows remain unaffected by the identity gate change
- [x] 5.5 Run relevant `user_management` and `orders` test modules and fix failures

## 6. Documentation

- [x] 6.1 Update `user_management/docs/backend/multi-provider-authentication.md` for identity gate, `verification_status`, social≠email ownership, and guest scope
- [x] 6.2 Update `user_management/docs/frontend/multi-provider-auth-integration.md` so clients use `identity_verified`, map the English API error to Bangla UI (e.g. অ্যাকাউন্ট যাচাই messaging), and do not force email verify for phone/social users
- [x] 6.3 Note that email verification remains for ownership/recovery/messaging only, not as the sole customer access requirement
