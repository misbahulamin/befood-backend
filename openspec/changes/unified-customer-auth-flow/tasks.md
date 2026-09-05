## 1. Baseline gap confirmation (reuse, do not rebuild)

- [x] 1.1 Confirm existing Google/Facebook/phone OTP/email deferred register/login/AuthSession paths remain the foundation; list only additive touch points (no duplicate OAuth/OTP stacks)
- [x] 1.2 Confirm phone OTP verify today create-or-logins by phone only (risk: logged-in social/email user verifying a new phone creates a second User) and document the bind gap for task 4.x

## 2. Shared phone_verification_required helper

- [x] 2.1 Add helper (e.g. `is_phone_verification_required(profile)`) based on `not profile.is_phone_verified`
- [x] 2.2 Extend `build_customer_auth_response()` to always include `phone_verification_required`
- [x] 2.3 Expose the same boolean on `/me` (and profile serializers that already surface onboarding) without removing existing fields

## 3. Onboarding alignment

- [x] 3.1 Update `get_onboarding_completion` so field `phone` is complete only when `is_phone_verified=True`
- [x] 3.2 Adjust any onboarding tests that assumed phone presence alone was enough

## 4. Authenticated phone bind (prevent duplicate accounts)

- [x] 4.1 Implement additive authenticated phone OTP bind path: logged-in customer without verified phone can send/verify OTP and attach canonical phone to **current** profile (`is_phone_verified=True`) instead of creating a new User
- [x] 4.2 Reject bind when the phone already belongs to a different customer (conflict `409` or existing project error shape); allow verify when phone already matches current profile
- [x] 4.3 Keep anonymous phone OTP create-or-login behavior unchanged for phone-first users
- [x] 4.4 Wire serializers/views/URLs/OpenAPI for the bind path (extend existing phone OTP endpoints with auth context **or** add additive bind endpoints—prefer minimal surface)

## 5. Email-first check API

- [x] 5.1 Add service: normalize email → return status `exists` | `pending` | `available` (no token, no password material)
- [x] 5.2 Add `POST` email-check endpoint under `user_management` with validation + throttling consistent with auth endpoints
- [x] 5.3 Add OpenAPI annotations and request/response examples

## 6. Post-email-verify phone signal

- [x] 6.1 After successful email OTP/link verification that finalizes pending registration, add additive `phone_verification_required` (and keep existing success `message`)
- [x] 6.2 Ensure email login path already carries the flag via unified builder (no separate duplicate logic beyond helper)

## 7. Tests

- [x] 7.1 Assert `phone_verification_required` on email login, Google new/existing, Facebook new/existing, phone OTP new/existing
- [x] 7.2 Google/Facebook new user without phone: account created, token issued, flag `true` (not blocked)
- [x] 7.3 Existing email user without phone: login `200` + token + flag `true`
- [x] 7.4 Email-check: exists / pending / available / invalid email
- [x] 7.5 Email verify response includes `phone_verification_required: true` for new customer without phone
- [x] 7.6 Authenticated phone bind: social/email user attaches phone without second User; conflict when phone owned elsewhere
- [x] 7.7 Regression: existing customer auth, admin, deliveryman tests still pass; tokens not invalidated by these changes

## 8. Documentation

- [x] 8.1 Update `user_management/docs/backend/multi-provider-authentication.md` (or additive companion doc) for email-check, phone gate flag, and bind flow
- [x] 8.2 Update frontend integration notes: unified envelope fields, when to show OTP, email-first sequence
- [x] 8.3 Document backward-compatibility guarantees (no forced logout, additive fields only)

## 9. Verification

- [x] 9.1 Run targeted `user_management` auth tests and fix failures
- [x] 9.2 Smoke checklist: Google new → phone required → bind OTP; email-check → register → verify → phone flag; legacy email login without phone still works
