## Why

BeFood’s wallet stack is **already live in production** with real customer balances, recharge/meal/withdraw history, and referral accounting. The prior deep audit identified finance risks (especially the legacy meal→Admin credit flag and ops gaps). Stakeholders now need an **updated, production-safe remediation plan** that hardens accounting without rewriting history or changing existing balances.

## What Changes

- **Update** the wallet deep-audit artifacts with production-live constraints and a safe improvement plan.
- Analyze **Issue 1:** remove / permanently disable `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` and related dead/legacy paths — without touching historical rows.
- **Confirm** the final custody accounting model (recharge/meal/withdraw/referral) as the locked business contract.
- Re-review Critical risks (silent referral failure, admin float shortage, direct balance writes) with **planning recommendations only**.
- Publish production safety / backward-compatibility tables and an **updated Must / Should / Optional roadmap**.
- **This phase still does not:** change application code, create migrations, modify production data, or rewrite historical transactions.
- Future code cleanup (flag removal, monitoring jobs) MUST be separate OpenSpec apply changes after this plan is accepted.

## Capabilities

### New Capabilities

- `wallet-system-audit-report`: End-to-end audit + updated production-safe remediation analysis deliverable.
- `wallet-financial-risk-register`: Critical / Medium / Low risks with production impact and plan-only remediations.
- `wallet-improvement-roadmap`: Updated Must / Should / Optional finance controls under live-production constraints.

### Modified Capabilities

- (none — planning/analysis only; no production behavior or API contract changes in this change)

## Impact

- **Artifacts only** under `openspec/changes/wallet-system-deep-audit/`.
- **Read scope:** `wallet/`, `admin_wallet/` (especially `ingestion.py`, `reconcile_admin_wallet_meal_payments`), `orders/services/meal_payment.py`, `referrals/services/commission.py`, `core/settings/base.py`, Django admin for wallet.
- **Production constraint:** any future implementation derived from this plan MUST preserve existing balances, transaction history, and accounting identity of completed rows.
- **Downstream:** a future apply change may safely remove/disable the meal-payment admin credit flag/code; monitoring/reconcile automation remains separate work.
