# Proposal

## Why

The twice-daily low-balance admin report (and related customer push/email) currently includes people with no active meal package—often showing Package `N/A` and near-zero balance—because `candidate_customers_queryset` also selects anyone with `meal_service_blocked_low_balance=True`, even after cancel or with no subscription. Ops and customers get noise; the “low balance” cohort must mean active subscribers only.

## What Changes

- Restrict wallet-threshold evaluation for meal-stop notify, low-balance reminder, and admin summary rows to customers who currently have an **active** `CustomerSubscription`.
- Exclude never-subscribed and cancelled (or otherwise non-active) customers from the admin low-balance report list, report count, and customer low-balance / meal-stop notifications for that cron path.
- Stop treating a leftover `meal_service_blocked_low_balance` flag alone as enough to appear in the report or receive threshold notifications; clear or silently ignore stale blocks for non-active subscribers so they are not counted as low-balance anywhere in this flow.
- On subscription cancel, clear the low-balance meal-service block when present so cancelled customers do not remain in the blocked cohort.
- Update backend docs and tests to lock the active-subscriber-only rule (including Package never listed as `N/A` solely because the row has no active subscription).

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `wallet-balance-threshold-cron`: Narrow cron evaluation so remind / stop notify / admin summary apply only to verified customers with an active meal subscription; do not keep cancelled/never-subscribed users in that cohort via the blocked-flag OR alone.
- `admin-low-balance-summary`: Admin report rows and headline user count MUST include only active subscribers who meet threshold rules; non-active customers MUST NOT appear (including Package `N/A` for missing subscription).
- `wallet-low-balance-reminder`: Explicitly exclude cancelled and never-subscribed customers from reminder push/email (requirement already implies active subscription; add exclusion scenarios).
- `wallet-meal-stop`: Meal-stop block/notify from the threshold cron MUST require an active subscription; clearing the block on cancel (and not notifying non-active customers) becomes required behavior.
- `meal-stop-low-balance-cron-push`: “Low Wallet Balance Alert” cron push MUST only fire for active subscribers under meal-stop evaluation.

## Impact

- Code: `orders/services/wallet_balance_thresholds.py` (`candidate_customers_queryset`, `run_wallet_threshold_check`, possibly cancel-path clear); `orders/services/subscription_service.py` (`cancel_subscription`); notification entrypoints already gated by the cron result; tests in `orders/tests/test_wallet_balance_thresholds.py` (+ cancel/block hygiene if covered elsewhere).
- Docs: `orders/docs/backend/wallet-balance-thresholds.md`.
- No public API contract change; behavior change is cron/report/notification eligibility only.
- Out of scope: redesigning kitchen meal-demand low-balance buckets (still delivery-scoped), changing threshold amounts, or admin UI settings.
