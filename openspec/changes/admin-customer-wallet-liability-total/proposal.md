# Proposal

## Why

Admins need a clear view of prepaid customer liability: the total money sitting across all customer wallets that has been recharged (or credited) but not yet consumed as meals or otherwise spent. Today `/admin/wallet` shows `net_customer_funding` (lifetime funding minus lifetime withdrawals), which does not subtract meal consumption and therefore overstates unconsumed prepaid balances. Without a live sum of customer wallet balances, ops cannot see how much prepaid cash is still owed to customers as unspent wallet credit.

## What Changes

- Add an additive Admin Wallet summary/dashboard metric that is the **sum of all customer `Wallet.balance` values** (prepaid unconsumed liability).
- Keep existing `net_customer_funding` and funding/withdrawal counters unchanged; document how the new metric differs from custody-lifetime `net_customer_funding`.
- Expose the metric on existing web Admin Wallet summary and dashboard responses (no new route required).
- Show the metric as a summary card on the Admin Panel `/admin/wallet` overview.
- Update Admin Wallet frontend/backend docs so the field meaning and card mapping are clear.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `admin-wallet-admin-api`: Admin Wallet summary/dashboard MUST include the live total of customer wallet balances as prepaid liability, distinct from `net_customer_funding`.
- `admin-wallet-frontend-docs`: Frontend docs MUST map the new field to an `/admin/wallet` overview card and explain that it is sum of customer wallet balances (unconsumed prepaid credit), not lifetime funding-minus-withdrawals.

## Impact

- **Backend:** `admin_wallet` summary/dashboard services, serializers, OpenAPI helpers, tests; aggregation over `wallet.Wallet.balance`.
- **APIs:** Additive fields on `GET /api/v1/web/admin-wallet/` and `GET /api/v1/web/admin-wallet/dashboard/` (verified-admin only).
- **Frontend (befood-frontend):** `AdminWalletPage` overview card, types, optional help copy distinguishing the new metric from Net customer funding.
- **Docs:** `admin_wallet/docs/frontend/admin-wallet.md` and related backend notes.
- **Non-goals:** Changing ledger accounting, recomputing `net_customer_funding`, per-customer liability breakdown UI, or excluding commission vs recharge in v1 (total uses stored `balance` = recharge + commission).
