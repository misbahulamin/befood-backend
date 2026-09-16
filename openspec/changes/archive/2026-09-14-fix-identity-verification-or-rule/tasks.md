## 1. Investigation and audit

- [x] 1.1 Trace email-only and phone-only paths: register → verify → login → `/me` → wallet recharge; note which flag mobile would see on Confirm Recharge
- [x] 1.2 Confirm screenshot Bangla copy maps to identity-incomplete FE guidance (not email-specific API text)
- [x] 1.3 Grep for residual AND / email-only hard gates on customer features (`is_email_verified` without OR helper, `phone_verification_required` used as permission)
- [x] 1.4 Document findings: soft `phone_verification_required` vs hard `identity_verified` gap on `/me`

## 2. Backend contract fixes

- [x] 2.1 Add `verification_status` via `build_verification_status` to `CurrentUserSerializer` (`/me`)
- [x] 2.2 Add the same `verification_status` to `CustomerExtendedProfileSerializer` (or shared helper to avoid drift)
- [x] 2.3 Fix any residual hard gate that requires both email and phone or email-only for identity access
- [x] 2.4 Keep `phone_verification_required` semantics as soft-only; do not change OR helper truth table

## 3. Regression matrix tests

- [x] 3.1 `/me` (or current-user) returns `identity_verified=true` and `phone_verification_required=true` for email-only verified customer
- [x] 3.2 `/me` returns `identity_verified=true` for phone-only verified customer
- [x] 3.3 Email-only customer passes wallet recharge identity gate (and at least subscribe or order identity permission)
- [x] 3.4 Phone-only customer passes the same matrix
- [x] 3.5 Neither factor → identity denial on a gated endpoint

## 4. Docs and mobile handoff

- [x] 4.1 Update multi-provider / identity frontend docs: hard-gate = `identity_verified`; soft = `phone_verification_required`; never AND email∧phone
- [x] 4.2 Write mobile checklist with Confirm Recharge example matching the production Bangla toast misuse
- [x] 4.3 Cross-link `wallet/docs/frontend/phone-verified-wallet-mobile-impact.md`
- [x] 4.4 State when mobile release is mandatory vs optional

## 5. Verification

- [x] 5.1 Run targeted user_management + wallet (+ subscribe/order if touched) tests
- [x] 5.2 Smoke: email-only → `/me` identity true → recharge allowed past identity
- [x] 5.3 Smoke: phone-only → same
- [x] 5.4 Confirm OpenAPI/docs for `/me` include `verification_status`
