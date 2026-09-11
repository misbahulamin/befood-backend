## Why

Phone-only customers can register, verify identity, and activate a subscription, but some never receive meal delivery slots—so service never starts despite a successful subscribe. Production must treat phone-or-email identity as valid, guarantee slot generation for every active subscription when menus are published, and remove leftover email-only filters that silently exclude phone users from ops automation.

## What Changes

- Deep-audit and document the full path: registration → CustomerProfile → subscription activation → `ensure_subscription_deliveries` → OrderDelivery / schedule generation.
- Confirm and harden the business rule: **email is optional**; phone-verified (or email-verified / social) identity is enough for subscribe and delivery generation.
- Fix residual `is_email_verified=True` gates in wallet-threshold and meal-close low-balance paths so phone-only active subscribers are included.
- Ensure slot creation depends on active CustomerProfile + active subscription + published menu (+ address snapshot rules), **not** on email presence.
- Add regression coverage: phone-only subscribe with published menu creates delivery slots; email-later-add does not duplicate slots.
- Provide a **read-only** production audit report for active subscriptions missing OrderDelivery rows (no destructive backfill/migration).
- Document mobile impact (likely none if APIs already return active customer) and optional admin “registration method” visibility.
- Update stale client docs that still say unverified email → 403.

## Capabilities

### New Capabilities

- `phone-only-customer-identity`: Phone-only (email blank) customers are first-class; identity verification is phone **or** email **or** social; email never required for subscribe or delivery generation.
- `subscription-delivery-slot-generation`: Active subscriptions must generate OrderDelivery slots when published menus exist; no email gate; idempotent ensure; clear failure modes when menus are unpublished.
- `phone-only-ops-parity`: Wallet-threshold, meal-close, and related ops queries include identity-verified phone-only customers (not email-only filters).
- `missing-delivery-slot-audit`: Read-only reporting for active subscriptions without delivery slots (counts + diagnosis: missing menu vs other), no production data mutation.

### Modified Capabilities

- (none — no existing main `openspec/specs/` capabilities cover this subscription/delivery identity contract)

## Impact

- **Backend:** `orders/services/subscription_service.py`, `orders/services/wallet_balance_thresholds.py`, `orders/services/meal_close.py`, `orders/api/subscription_serializers.py` / permissions, `user_management` identity helpers, related tests and docs.
- **Ops:** Cron `ensure_subscription_deliveries`; meal publish → ensure-all path; read-only SQL/management report for missing slots.
- **Mobile:** Likely no mandatory change if registration/subscribe APIs already succeed for phone-only; optional address-complete warning only (never force email).
- **Admin:** Display of blank email must remain valid; optional registration-method field for support.
- **Data safety:** No email backfill, no subscription reset, no order rewrite migrations; future-flow + filter fixes only; optional safe re-run of ensure after menu publish for affected users.
