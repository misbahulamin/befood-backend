## Why

Production mobile users who completed **either** email verification **or** phone OTP still see a Bangla “account verification incomplete” error when using protected features such as wallet recharge (screenshot: Confirm Recharge). Product rule is **OR** (`email_verified OR phone_verified`, plus social), but clients appear to treat verification as **AND**—or they hard-block on the soft flag `phone_verification_required`. Backend helpers already implement OR for permissions, but `/me` and profile responses omit `verification_status.identity_verified`, so mobile cannot reliably apply the correct hard-gate rule after login.

## What Changes

- Enforce and document a single production contract: **identity verified = email OR phone OR Google OR Facebook** (never email AND phone).
- Full-path audit: registration, email verify, phone OTP, login, token, `/me`/profile, wallet/subscribe/order permissions, any residual AND checks.
- Expose `verification_status` (including `identity_verified`) on authenticated customer `/me` and profile reads so clients do not invent AND logic from raw flags + `phone_verification_required`.
- Clarify soft vs hard gates: `phone_verification_required` prompts phone bind only; it MUST NOT mean “blocked from wallet/subscribe/orders” when `identity_verified` is true.
- Add matrix regression tests: email-only and phone-only users can recharge, subscribe, and pass identity permissions; neither factor → denied.
- Ship a **mobile app update plan**: hard-gate only on `identity_verified === false`; never require both email and phone; map Bangla copy only when identity is false.
- Align with (do not duplicate) wallet-scoped work in `phone-verified-wallet-access`.

## Capabilities

### New Capabilities

- `identity-verification-or-rule`: Canonical OR identity contract across auth envelope, `/me`/profile, and customer feature gates; soft phone prompt vs hard identity block; email-only and phone-only matrix coverage; mobile integration contract.

### Modified Capabilities

- (none in main `openspec/specs/` — existing wallet/order specs say “verified customer” without defining email∧phone; this change introduces the explicit OR capability rather than rewriting those resource specs)

## Impact

- **Backend:** `user_management` (`CurrentUserSerializer`, profile serializers, `auth_session`, `identity_verification`), customer permission classes (`IsVerifiedCustomer` / `IsVerifiedWalletCustomer`), wallet/orders/subscription smoke paths, docs under `user_management/docs` and wallet frontend identity notes.
- **APIs (additive):** `/me` and customer profile gain `verification_status` (or equivalent top-level `identity_verified`) — **not BREAKING** if clients ignore unknown fields.
- **Mobile (separate repo):** Required if app blocks on `phone_verification_required` or `email_verified && phone_verified`; plan documented in backend frontend docs for handoff.
- **Related changes:** Builds on `remove-email-verification-dependency`, `unified-customer-auth-flow`, `phone-verified-wallet-access`.
- **Out of scope:** Forcing phone collection as a hard block for email-only users; deliveryman/admin verification; rewriting historical user rows.
