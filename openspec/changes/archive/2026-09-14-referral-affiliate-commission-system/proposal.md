## Why

BeFood needs a growth loop where active meal subscribers invite new customers and earn commission on each successfully consumed meal. The backend currently has no referral, attribution, or commission capability, and the customer wallet is a single spendable balance—so commission cannot be credited without risking cash withdrawal of non-cash promotional funds.

## What Changes

- Add a new `referrals` Django app for referral codes, immutable attribution relationships, commission ledger, and eligibility/validation rules.
- Auto-generate a globally unique referral code for every customer using format `BEF` + **8** uppercase alphanumeric characters (e.g. `BEF8A92KX`); code validity depends on the referrer’s active meal subscription.
- Allow referral attribution only on **mobile** registration paths (phone OTP, social, and mobile email finalize); reject referral codes from web registration with `422`.
- Persist pending referral intent on email signup (`referral_code`, `referrer_snapshot_id`, timestamp) and **re-check eligibility at finalize**.
- When a referred customer’s meal delivery is marked `delivered` and charged, credit the referrer’s wallet with a configurable percentage (default **5%**) of the charged meal price—only if both parties still have an active meal subscription.
- Atomically debit the platform Admin Wallet and credit the referrer’s **commission balance** with idempotency keyed to the delivery.
- `ReferralCommission` uses explicit statuses: `pending`, `success`, `failed`, `skipped`, `reversed`, with schema support for linked reversal wallet transactions (delivery cancel / correction path).
- Admin can create **manual referral adjustments** (+/−) with required reason and audit trail; finance can **CSV-export** commission reports.
- Admin analytics include financial totals **and** growth conversion metrics (validations, successful registrations, paid subscribers from referral, conversion rate). Optional share counters on `ReferralProfile` (`share_count`, `last_shared_at`).
- **BREAKING (customer wallet contract):** Split into `recharge_balance` (withdrawable) and `commission_balance` (meal-spendable, not withdrawable); keep `balance` as denormalized total. Migration MUST set `recharge_balance = balance`, `commission_balance = 0`, validate `balance == recharge + commission` for every wallet, and ship `verify_wallet_balance_consistency`. Ledger rows MUST record total and bucket after-balances consistently.
- Explicit DB indexes for referral list/analytics queries (no `ReferralStatistics` table in v1).
- Validate API: rate limit including IP-based throttle (device throttle reserved for future).
- Hook commission accrual into `mark_delivery` after successful meal charge (Onahar pattern); support reconcile + reversal plumbing.

## Capabilities

### New Capabilities

- `referral-program`: Referral code lifecycle (`BEF`+8), mobile-only attribution, pending snapshot fields, one immutable referrer per customer, optional share tracking fields, eligibility tied to active `CustomerSubscription`.
- `referral-commission`: Per-delivery accrual, status machine (`pending`/`success`/`failed`/`skipped`/`reversed`), Admin Wallet debit + commission-bucket credit, reversal/manual adjustment support, idempotency, indexes.
- `referral-customer-api`: Customer me/link/validate/stats/history; IP-throttled validate endpoint.
- `referral-admin-api`: Admin analytics (finance + conversion), filters, per-customer detail, manual adjustment, CSV export.

### Modified Capabilities

- `customer-wallet`: Dual buckets; ledger invariant and per-txn bucket after-balances; migration verification command.
- `wallet-funding`: Withdraw limited to `recharge_balance`; recharge credits only recharge bucket; commission never withdrawable / never customer-funding custody.

## Impact

- **New app:** `referrals/` (models, services, API, admin, docs, tests); `INSTALLED_APPS` + `core/urls.py`.
- **Touched apps:** `user_management` (pending snapshot + phone/social hooks), `wallet` (buckets, ledger snapshots, verify command), `admin_wallet` (commission expense + reversal types), `orders` (`mark_delivery` hook / future reverse path).
- **Ops:** `verify_wallet_balance_consistency`, `reconcile_referral_commissions`, referral code backfill.
- **Config:** `REFERRAL_ENABLED`, `REFERRAL_COMMISSION_PERCENT` (default `5`), `REFERRAL_LINK_BASE_URL`, mobile client gate.
- **Future (schema reserved / not blocking v1):** device-id fraud flags, richer click tracking beyond validate events.
