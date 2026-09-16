## 1. Shared meal-stop evaluation helper

- [x] 1.1 Add a single-customer stop evaluator in `orders/services/wallet_balance_thresholds.py` (reuse `spendable_balance`, `get_order_wallet_settings`, `apply_meal_service_block`) that blocks when post-debit balance is strictly below `meal_stop_threshold`
- [x] 1.2 On newly blocked only, invoke existing meal-stop customer notify helpers best-effort (prefer `on_commit`); never raise into the charge path; do not run reminder/admin-summary from this helper
- [x] 1.3 Confirm helper does not resume on debit (resume stays credit/cron via `maybe_resume_after_wallet_credit` / `run_wallet_threshold_check`)

## 2. Wire into meal-delivery payment

- [x] 2.1 After a successful real debit in `charge_delivered_meal` (`orders/services/meal_payment.py`), call the evaluator with the delivery customer once post-debit balance is visible
- [x] 2.2 Skip evaluation on idempotent already-charged re-attach paths that do not debit again; skip when charging is disabled by settings
- [x] 2.3 Verify operator mark-delivered (`order_delivery.mark_delivery` → charge) and auto-delivery (`run_auto_delivery`) both inherit the hook without duplicate calls per successful debit

## 3. Tests

- [x] 3.1 Test: successful lunch/dinner charge that drops balance below `meal_stop_threshold` sets `meal_service_blocked_low_balance=true` immediately
- [x] 3.2 Test: successful charge that leaves balance `>= meal_stop_threshold` does not block
- [x] 3.3 Test: insufficient-funds mark-delivered rejection does not apply post-charge meal-stop via the charge path
- [x] 3.4 Test: after immediate block, kitchen today demand / `final_cooking_count` excludes the customer before any wallet-threshold cron run
- [x] 3.5 Test: notify failure after block does not roll back charge or clear the block flag
- [x] 3.6 Ensure existing auto-delivery eligibility (skip already-blocked) and twice-daily cron tests still pass

## 4. Docs and verification

- [x] 4.1 Update backend docs (wallet-threshold / meal-delivery / meal-demand kitchen as appropriate) to document post-charge meal-stop and that 15:00 is deliver+charge (not slot creation)
- [x] 4.2 Note that 08:00/20:00 `check_wallet_balance_thresholds` cron remains required; no crontab schedule change for this fix
- [x] 4.3 Run targeted test modules and record results; no database migration expected
