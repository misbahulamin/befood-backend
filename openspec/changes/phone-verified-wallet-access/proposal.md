## Why

Phone-registered customers can complete OTP and log into the mobile app, but wallet recharge submit (`POST /wallet/recharge/` with amount + transaction id) still fails with a “verify first before recharge” style error. Product intent is clear: if identity was established via phone OTP, email verification must not be required for wallet (or other authenticated customer) actions. Prior identity work exists (`remove-email-verification-dependency`), but wallet funding still lacks phone-only regression coverage, wallet-specific gate messaging, and client/docs alignment—so phone users keep hitting the verification wall in production.

## What Changes

- Harden the rule that **phone-verified identity alone** satisfies customer wallet access (balance, history, recharge, withdraw)—email must never be mandatory for phone-registered accounts.
- Audit and close any remaining email-only gates, stale “verified = email” assumptions, or permission/message mismatches on wallet customer endpoints.
- Ensure phone OTP registration continues to set `is_phone_verified=True` and that `IsVerifiedCustomer` / `is_customer_identity_verified` treat those users as allowed for funding.
- Add wallet-specific identity-denied error copy (not order-placement wording) so mobile can show accurate Bangla UX.
- Add regression tests: phone-only customer can submit recharge; email-unverified + phone-unverified remains blocked.
- Update wallet frontend/backend docs so “verified customer” means identity-verified (phone **or** email **or** social), not email-only.
- Produce a **mobile app impact plan**: stop client-side email-verification gates before recharge; rely on `verification_status.identity_verified` / `phone_verified`; map new 403 copy.

## Capabilities

### New Capabilities

- `phone-verified-wallet-access`: Phone-OTP–verified customers can use wallet balance, history, and manual funding (recharge/withdraw) without email verification; clear identity-denied contract for wallet; regression coverage and client guidance.

### Modified Capabilities

- `wallet-funding`: Clarify that customer recharge/withdraw permission uses unified identity verification (phone or email or social), not email-only.
- `customer-wallet`: Clarify that wallet read access uses the same identity rule for phone-only accounts.

## Impact

- **Backend:** `orders.api.permissions.IsVerifiedCustomer`, `user_management.services.identity_verification`, `wallet/api/views.py` (and related serializers/docs), phone OTP / customer factory path confirmation, wallet tests.
- **APIs (contract clarify, non-breaking for email-verified users):** `GET/POST` customer wallet + `POST /wallet/recharge/` + `POST /wallet/withdraw/` — phone-verified users must succeed when otherwise eligible; identity-denied 403 message may be improved for wallet contexts.
- **Docs:** `wallet/docs/frontend/*`, related backend auth/identity docs.
- **Mobile app (separate repo):** planned follow-up—remove email-must-verify UX before recharge; use `identity_verified` / `phone_verified`; optional copy update for new 403 detail. No mandatory mobile change if app already trusts backend and does not gate on email.
- **Related changes:** builds on `remove-email-verification-dependency` and aligns with `phone-only-subscription-delivery-slot` (subscribe/ops); this change is wallet-funding–scoped.
- **Out of scope:** Changing admin funding review; requiring phone for email-only users; forcing email collection on phone accounts; rewriting historical ledger rows.
