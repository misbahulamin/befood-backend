# Tasks

## 1. Candidate eligibility and cancel hygiene

- [x] 1.1 Tighten `candidate_customers_queryset` in `orders/services/wallet_balance_thresholds.py` to verified active users with an **active** `CustomerSubscription` only (remove the `meal_service_blocked_low_balance` OR), and verify a cancelled/never-subscribed profile with the block flag set is not returned by the queryset helper or a small unit assertion.
- [x] 1.2 In `cancel_subscription`, clear `meal_service_blocked_low_balance` / `meal_service_blocked_at` when present after a successful cancel transition (idempotent for already-cancelled), and verify with a cancel test that the flag is false afterward.
- [x] 1.3 Add a one-shot cleanup for existing orphans (customers with the block flag but no ACTIVE subscription)—either a short data migration, management command step, or documented clear inside the threshold run—and verify blocked non-subscribers are cleared without sending notifications.

## 2. Cron / admin report behavior + tests

- [x] 2.1 Ensure `run_wallet_threshold_check` only reminds, meal-stops/notifies, and builds admin `affected` rows for active subscribers; verify cancelled (or never-subscribed) customers below thresholds produce no customer push/email and no admin-report row.
- [x] 2.2 Extend `orders/tests/test_wallet_balance_thresholds.py` with cases for: cancelled subscriber with leftover block + low balance omitted from admin mail subject/count and body; active subscriber still listed with real package name; dry-run unchanged for active cases—run the test module and confirm pass.
- [x] 2.3 Update `orders/docs/backend/wallet-balance-thresholds.md` to state active-subscriber-only eligibility for cron notify + admin report (and cancel clears block); verify the doc matches the implemented queryset / cancel behavior.

## Workflow follow-up

- Archive the change after implementation review is satisfied.
- Sync or archive delta specs into main specs per project OpenSpec practice.
