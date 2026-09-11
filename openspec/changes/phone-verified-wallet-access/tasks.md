## 1. Audit and confirm root cause

- [x] 1.1 Reproduce or trace phone-register → login → `POST /wallet/recharge/` path; capture actual HTTP status and `detail` when identity fails
- [x] 1.2 Grep wallet customer views, permissions, serializers, and funding services for email-only gates (`is_email_verified`, “Email verification is required”)
- [x] 1.3 Confirm `create_phone_only_customer` / `verify_phone_otp` still set `is_phone_verified=True` and CUSTOMER group membership
- [x] 1.4 Confirm `IsVerifiedCustomer` already uses `is_customer_identity_verified`; note any wallet-specific gap

## 2. Backend identity gate and messaging

- [x] 2.1 Add wallet-scoped identity-denied English message constant (recharge/wallet wording, not order-placement or email-only)
- [x] 2.2 Apply that message on customer wallet endpoints (balance, transactions, recharge, withdraw) without weakening phone/email/social OR rule
- [x] 2.3 Fix any residual email-only hard gate found in audit that blocks phone-verified wallet access
- [x] 2.4 Leave email ownership, recovery, and messaging flows unchanged

## 3. Regression tests

- [x] 3.1 Add API test: phone-only customer (`is_phone_verified=True`, email blank/unverified) can `GET` wallet and `POST` recharge (identity gate passes)
- [x] 3.2 Add API test: same customer can reach withdraw permission gate (identity passes; other business rules may still apply)
- [x] 3.3 Add API test: customer with no email/phone/social verification gets `403` identity denial on recharge with non-email-only copy
- [x] 3.4 Adjust wallet test helpers if they only seed `is_email_verified` so phone-only fixtures are reusable

## 4. Docs and mobile impact plan

- [x] 4.1 Update `wallet/docs/frontend/` (customer-wallet / manual-funding) so “verified” means identity-verified (phone or email or social), not email-only
- [x] 4.2 Document wallet identity `403` English copy and recommended Bangla UX (do not tell phone users to verify email)
- [x] 4.3 Write mobile impact checklist: remove client email hard-gate before recharge; use `identity_verified` / `phone_verified`; soft email upsell only
- [x] 4.4 Note in docs if no mandatory mobile code change is needed when app already trusts backend

## 5. Verification

- [x] 5.1 Run targeted wallet + identity-related tests
- [x] 5.2 Manual smoke: phone OTP register → recharge submit → pending funding (not identity 403)
- [x] 5.3 Manual smoke: fully unverified customer still blocked with new wallet identity message
- [x] 5.4 Confirm OpenAPI / schema notes for wallet 403 descriptions still accurate after message change
