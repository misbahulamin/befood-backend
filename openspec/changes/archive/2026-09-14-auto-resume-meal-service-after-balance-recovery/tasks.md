## 1. Investigation & wiring (resume)

- [x] 1.1 Confirm `approve_recharge` insertion point after balance credit vs `credit_wallet` on_commit resume
- [x] 1.2 Verify `maybe_resume_after_wallet_credit(CustomerProfile | None) -> bool` and that it uses `spendable_balance` → `Wallet.balance` + live `meal_stop_threshold` (same as cron); do not add duplicate balance math

## 2. Approval resume behavior

- [x] 2.1 In `approve_recharge`, call `restored = maybe_resume_after_wallet_credit(profile)` inside the same atomic after credit; drive `meal_service_restored` from that boolean (no extra flag query)
- [x] 2.2 Ensure reject / pending create / withdraw approve do not clear meal-stop flags and do not claim restore
- [x] 2.3 Do not add a “meal service restored” customer notification; leave existing recharge-approved notifications unchanged
- [x] 2.4 Leave auto meal delivery skip-on-block unchanged; no DB migration

## 3. Admin API contract

- [x] 3.1 Expose additive `meal_service_restored` on successful admin funding approve responses
- [x] 3.2 Update OpenAPI / serializer docs for the approve action

## 4. Meal-stop cron low-balance push

- [x] 4.1 Change meal-stop cron branch so every non-dry-run evaluation with `balance < meal_stop_threshold` sends the Low Wallet Balance Alert push (including already-blocked customers)
- [x] 4.2 Implement required title/body with `{customer_full_name}`; do not gate this push on `last_low_balance_reminder_on`
- [x] 4.3 Keep meal-stop block apply/ensure behavior and auto-delivery skip semantics; push failures must not undo the block
- [x] 4.4 Leave the separate once-per-day reminder-threshold path unchanged unless explicitly in scope

## 5. Tests

- [x] 5.1 Test: blocked + sufficient approve → balance up, block cleared, `meal_service_restored=true`, no restore notification
- [x] 5.2 Test: blocked + insufficient approve → still blocked, `meal_service_restored=false`
- [x] 5.3 Test: unblocked approve → flags unchanged, `meal_service_restored=false`
- [x] 5.4 Test: latest `meal_stop_threshold` used at approve time
- [x] 5.5 Test: pending/reject do not resume; withdraw approve does not claim restore
- [x] 5.6 Test: morning cron below meal-stop → push sent + blocked
- [x] 5.7 Test: second cron same day still below meal-stop → another push sent
- [x] 5.8 Test: balance `>=` meal-stop after resume → no meal-stop-band alert on that cron evaluation

## 6. Documentation

- [x] 6.1 Update admin/frontend wallet funding docs: `meal_service_restored`, optional “Meal service restored” toast, backend-owned resume, no customer-app change
- [x] 6.2 Update wallet-balance-threshold docs: every-run meal-stop-band push copy/rules; note approve resume sync vs `credit_wallet` on_commit; no migration
