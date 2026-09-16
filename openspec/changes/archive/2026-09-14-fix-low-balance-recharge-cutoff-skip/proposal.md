## Why

When a low-balance-blocked customer recharges after a meal-off cutoff has already passed, `maybe_resume_after_wallet_credit` clears `meal_service_blocked_low_balance` based only on wallet balance. Kitchen demand then treats their still-`scheduled` delivery as cookable, so `final_cooking_count` (and ingredient kg) can jump after the kitchen has already planned without them. Financial resume and retroactive meal reactivation must be separated.

## What Changes

- After a successful low-balance meal-stop resume (recharge approve, `credit_wallet` on_commit, or cron resume), evaluate today's lunch/dinner against live `MealOffSettings` cutoffs in the settings timezone (not hardcoded times).
- For each `(service_date, meal_period)` whose cutoff is already past: keep that slot ineligible for kitchen/auto-delivery by applying a **date+period-specific** system skip on the existing `OrderDelivery` (idempotent; no duplicate rows).
- For slots whose cutoff has not passed: leave existing meal ON/OFF preference alone — do not force meal-on; do not permanently flip subscription preferences.
- Clear `meal_service_blocked_low_balance` when spendable balance recovers (existing resume rule) so the customer is financially active again, without re-including already-cutoff-passed meals in cook counts.
- Keep `meal_stop_threshold` / meal-off times sourced from settings; preserve atomic payment/funding flows and cron coexistence.
- Add tests for before/after cutoff resume, lunch-only vs both meals skipped, exact cutoff boundary, manual meal-off preservation, next-day non-carry, idempotent multi-approve, and kitchen/ingredient consistency.
- No **BREAKING** API field renames; kitchen response shape stays the same (counts must stop incorrectly rising after late recharge).

## Capabilities

### New Capabilities

- `low-balance-recharge-cutoff-skip`: On low-balance meal-stop resume after wallet credit recovery, clear the financial block when threshold is met, then skip only today's already-cutoff-passed meal slots via existing delivery skip semantics without changing permanent meal preferences.

### Modified Capabilities

- `kitchen-cooking-requirement`: After late recharge resume, `final_cooking_count` and ingredient quantities MUST NOT increase for a meal period whose meal-off cutoff has already passed for that service date.
- `meal-demand-forecasting`: Shared demand math MUST continue to exclude system-skipped post-cutoff slots from final cooking (and treat them consistently with other skips vs low-balance-blocked counts).

## Impact

- **Primary services:** `orders/services/wallet_balance_thresholds.py` (`maybe_resume_after_wallet_credit` / clear path), likely a small helper reusing `orders/services/meal_off.py` (`is_past_meal_cutoff`, `meal_off_business_now`, `CUTOFF_PASSED_NOTE`).
- **Call sites (inspect, keep atomic):** `wallet/services/funding.py` (`approve_recharge`), `wallet/services/ledger.py` (`credit_wallet` on_commit), wallet-threshold cron resume branch.
- **Models reuse:** `OrderDelivery` status/`skip_source`/`note`; `CustomerProfile.meal_service_blocked_low_balance` (`True` = blocked, `False` = not blocked — do not invert); `MealOffSettings`; `OrderWalletSettings.meal_stop_threshold`.
- **APIs:** No new endpoints; kitchen `GET .../today-meal-requirement/` counts stabilize after late recharge; funding approve may still return existing `meal_service_restored`.
- **DB:** Prefer **no migration** if existing delivery skip fields suffice; add a field only if audit requires a distinct skip reason beyond `note=cutoff_passed`.
- **Frontend:** No required customer/admin UI change for this fix.
- **Cron:** No schedule change required; ensure resume-from-cron applies the same cutoff skip helper.
- **Tests/docs:** Threshold resume + meal demand/kitchen tests; backend wallet-threshold / meal-demand docs.
