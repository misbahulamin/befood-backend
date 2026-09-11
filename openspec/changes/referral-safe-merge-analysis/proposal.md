## Why

`unfinished-features` holds a nearly complete Referral/Affiliate + dual-bucket wallet implementation, but it diverged from production before three `production-hotfix` merges landed on `origin/main`. A naive merge risks breaking live wallet accounting (provider-ref uniqueness, meal-service resume on recharge approve) and will hit a hard Django migration number collision on `wallet.0004`. We need a documented safe-integration plan before any code lands on production.

## What Changes

- Document a complete branch-diff, conflict, migration, and wallet-risk analysis for integrating referral work into latest `origin/main` (no production merge in this change’s analysis phase).
- Define a safe integration workflow: new branch from `origin/main`, selective port of referral + dual-bucket wallet, explicit preservation of production-hotfix wallet fixes.
- Require renumbering/rebasing of unfinished wallet migrations so they depend on production’s `0004_live_status_provider_recharge_ref_unique` instead of colliding with it.
- Require dual-bucket wallet behavior to keep production invariants: live-status provider recharge uniqueness, meal-service auto-resume on approve, withdraw/recharge accounting safety.
- Treat `db.sqlite3` as non-mergeable noise; never commit local SQLite as part of integration.
- **BREAKING (when later applied to production):** customer wallet API gains `recharge_balance` / `commission_balance` / `withdrawable_balance`; withdraw limited to recharge bucket; meal payments consume commission first.

## Capabilities

### New Capabilities

- `referral-safe-integration`: Branch strategy, conflict resolution order, migration sequencing, and verification gates required before enabling referral accrual in production.
- `wallet-dual-bucket-compat`: Dual-bucket wallet + referral commission must coexist with production-hotfix wallet accounting (provider-ref live uniqueness, funding approve resume hook, ledger invariants).

### Modified Capabilities

- `customer-wallet`: Dual buckets and ledger after-balance snapshots (from unfinished referral work) while retaining production constraint semantics.
- `wallet-funding`: Withdraw/recharge paths become bucket-aware without dropping production provider-ref and meal-resume behavior.

## Impact

- **Branches:** `origin/main` (includes merged production-hotfix), local-only `unfinished-features` (1 WIP commit), local `main` may be stale vs remote.
- **Apps:** `referrals` (new), `wallet`, `admin_wallet`, `user_management`, `orders` (`mark_delivery` hook), `core` (settings/urls).
- **Migrations:** wallet `0004` number collision is the highest operational risk; admin_wallet `0005` and user_management `0021` / referrals `0001` are additive if sequenced correctly.
- **Production data:** dual-bucket data migration copies existing `balance` → `recharge_balance`; commission starts at 0; provider-ref constraint already applied on main must remain.
- **Out of scope for this change’s analysis artifacts:** executing merge/commits/deploy (deferred to apply phase / operator approval).
