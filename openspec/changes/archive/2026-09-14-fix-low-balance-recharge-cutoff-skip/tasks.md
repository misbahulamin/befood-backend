## 1. Codepath verification

- [x] 1.1 Re-confirm flag semantics in code/docs: `meal_service_blocked_low_balance=True` means blocked; `False` means not blocked (do not invert)
- [x] 1.2 Map all resume/clear call sites: `maybe_resume_after_wallet_credit`, `approve_recharge`, `credit_wallet` on_commit, cron `clear_meal_service_block`, any admin manual clear
- [x] 1.3 Confirm kitchen/demand math for blocked vs skipped (`meal_demand.py`) and meal-off helpers (`is_past_meal_cutoff`, `CUTOFF_PASSED_NOTE`)

## 2. Core resume + cutoff skip

- [x] 2.1 Add idempotent helper to system-skip today’s past-cutoff cookable `OrderDelivery` slots for a customer (reuse `MealOffSettings` timezone/times + `is_past_meal_cutoff`; no hardcoded `02:00`/`16:00`/`100`)
- [x] 2.2 Wire helper into shared resume path after successful low-balance block clear (`maybe_resume_after_wallet_credit` and/or extracted resume function)
- [x] 2.3 Route wallet-threshold cron resume through the same clear + cutoff-skip path (do not leave cron on bare `clear_meal_service_block` only)
- [x] 2.4 Ensure helper never meal-ons customer/admin skips, never flips permanent preferences, never creates duplicate deliveries
- [x] 2.5 Keep funding/credit transactions intact (atomic approve flow; best-effort resume posture preserved where already used)

## 3. Kitchen / demand consistency check

- [x] 3.1 Verify late resume moves customer from low-balance blocked into skipped/meal-off for past-cutoff slots without raising `final_cooking_count`
- [x] 3.2 Verify ingredient kg in kitchen today-requirement stay consistent with unchanged final cooking for that past-cutoff period
- [x] 3.3 Verify dinner can still count when lunch is past-cutoff but dinner cutoff has not passed

## 4. Tests

- [x] 4.1 Balance `< meal_stop_threshold` applies/keeps low-balance block
- [x] 4.2 Recharge before lunch cutoff → today’s lunch remains eligible if previously ON/`scheduled`
- [x] 4.3 Recharge after lunch cutoff → today’s lunch system-skipped; `final_cooking_count` does not increase
- [x] 4.4 After lunch cutoff, before dinner cutoff → lunch skipped, dinner eligible if ON
- [x] 4.5 After both cutoffs → today’s lunch and dinner skipped
- [x] 4.6 Resume exactly at cutoff → period still eligible (strict-after deadline rule)
- [x] 4.7 Customer manual meal-off preserved (resume does not force meal-on)
- [x] 4.8 Next business day → prior day’s cutoff skips do not carry forward as new skips
- [x] 4.9 Multiple approve/resume calls → idempotent; no duplicate deliveries / status thrash
- [x] 4.10 Kitchen API + ingredient quantity consistency with final cooking after late resume

## 5. Docs and wrap-up

- [x] 5.1 Update backend wallet-threshold / meal-demand docs: financial resume ≠ past-cutoff kitchen reactivation; blocked→meal_off count shift
- [x] 5.2 Confirm no API contract / frontend / cron schedule changes required (or document any additive fields if introduced)
- [x] 5.3 Confirm migration decision (prefer none); run targeted tests and note results in apply report
