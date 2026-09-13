## Context

Verified flag semantics in code (`CustomerProfile.meal_service_blocked_low_balance`):

- `True` = meal service **blocked** for low balance (auto-delivery skip; kitchen demand puts the customer in `low_balance_blocked_count`, not `final_cooking_count`).
- `False` = **not** blocked.

Current resume path:

1. Admin `approve_recharge` credits wallet then calls `maybe_resume_after_wallet_credit`.
2. `credit_wallet` also schedules `maybe_resume_after_wallet_credit` on commit.
3. Twice-daily `run_wallet_threshold_check` clears the block via `clear_meal_service_block` when balance `>= meal_stop_threshold`.

`maybe_resume_after_wallet_credit` / cron clear **only** compare spendable balance to `OrderWalletSettings.meal_stop_threshold`. They do not consult `MealOffSettings` lunch/dinner cutoffs.

Kitchen `get_demand` / `build_kitchen_requirement` treats non-skipped, non-blocked deliveries as cookable. After late resume, a still-`scheduled` lunch/dinner slot re-enters `final_cooking_count` and ingredient kg — even when that period’s meal-off deadline already passed.

Existing building blocks to reuse (do not duplicate):

- `meal_off_business_now`, `meal_off_deadline`, `is_past_meal_cutoff`, `CUTOFF_PASSED_NOTE` in `orders/services/meal_off.py`
- `OrderDelivery` `status=skipped` + `skip_source=system` (same pattern as `ensure_subscription_deliveries` post-cutoff slot creation)
- Threshold helpers in `orders/services/wallet_balance_thresholds.py`

## Goals / Non-Goals

**Goals:**

- Separate **financial meal-stop clear** from **retroactive kitchen eligibility**.
- On every successful low-balance resume, skip today’s already-cutoff-passed slots for that customer only.
- Keep future slots and permanent preferences unchanged.
- Keep kitchen `final_cooking_count` (and ingredient scaling) stable for periods whose cutoff already passed.
- Remain idempotent under repeated approve/credit/cron resume.
- Use configured timezone and threshold/cutoff settings only.

**Non-Goals:**

- Changing meal-off settings API, wallet settings API response shapes, or kitchen response field names.
- Permanently turning lunch/dinner preference OFF.
- Backfilling historical kitchen snapshots already taken before the fix.
- Redesigning low-balance block application, reminder push frequency, or auto-delivery cron schedules.
- Inventing a second parallel “skip registry” model when `OrderDelivery` already models per-slot state.

## Decisions

### 1. Shared resume helper that clears block then applies cutoff skips

**Choice:** Introduce a single service entry used by credit resume and cron resume (e.g. extend `maybe_resume_after_wallet_credit` and route cron’s clear branch through the same post-clear cutoff step, or extract `resume_meal_service_after_balance_recovery(customer) -> bool`).

**Steps when balance recovered and block was present:**

1. Clear `meal_service_blocked_low_balance` / `meal_service_blocked_at` (existing semantics).
2. Resolve business `now` via `meal_off_business_now(get_meal_off_settings())`.
3. For each of today’s `lunch` and `dinner`, if `is_past_meal_cutoff(service_date, meal_period)`:
   - Locate the customer’s non-cancelled `OrderDelivery` for that `(service_date, meal_period)`.
   - If status is still cookable (`scheduled` / equivalent non-terminal non-skipped), set `skipped` + `skip_source=system` + `note=CUTOFF_PASSED_NOTE` (or an equally stable audit token) + `marked_at`.
   - If already `skipped` / delivered / missed: no-op (preserve customer/admin skip).
4. Periods not past cutoff: do nothing to the delivery (do **not** meal-on).

**Why over alternatives:**

- Flipping a global preference OFF would wrongly disable tomorrow’s meals.
- Leaving the delivery `scheduled` after unblock is the root bug.
- A new daily-override table would duplicate `OrderDelivery` slot identity.

### 2. Exact cutoff boundary matches existing meal-off gating

**Choice:** Treat `now <= deadline` as still eligible (same as `can_meal_off` / `is_past_meal_cutoff` which uses strict `>`). Recharge exactly at cutoff restores that meal if preference is ON.

### 3. Count taxonomy after late resume

**Choice:** Accept that a late-resumed customer moves from `low_balance_blocked_count` into `meal_off_count` (system skip), while `final_cooking_count` stays flat. Document this so ops do not expect blocked count to remain elevated after financial restore.

### 4. No migration unless audit forces it

**Choice:** Prefer existing `OrderDelivery` fields. Add a dedicated `skip_reason` column only if product requires machine-distinct reason beyond `note` + `skip_source=system`. Default plan: **no migration**.

### 5. Do not force meal-on; do not invent deliveries

**Choice:** If the slot is already customer/admin skipped, leave it. If no delivery row exists, do not create one solely for skip bookkeeping — absence already means no kitchen count; future `ensure_subscription_deliveries` already creates past-cutoff slots as skipped.

### 6. Concurrency

**Choice:** Apply skips inside the same atomic section as the clear when possible (`select_for_update` on profile + delivery rows). Multiple resumes must be idempotent (second call finds already-skipped rows). Never break `approve_recharge` / `credit_wallet` transaction contracts; if resume stays best-effort on commit, cutoff skip must share that same best-effort posture but still be deterministic when it runs.

## Risks / Trade-offs

- **[Risk] Cron clears via `clear_meal_service_block` today, bypassing `maybe_resume_after_wallet_credit`** → Mitigation: both resume paths MUST call the shared post-resume cutoff helper.
- **[Risk] Customer meal-on after system skip** → Mitigation: `can_meal_on` already allows only `skip_source=customer`; system skips cannot be meal-oned by the customer after cutoff (and after cutoff `can_meal_on` is false anyway). Confirm admin override paths remain intentional.
- **[Risk] Ops confusion: meal_off_count rises when blocked count falls** → Mitigation: document in backend wallet-threshold / meal-demand docs; kitchen final cook number is the operational truth.
- **[Risk] Hardcoding times/threshold in tests or code** → Mitigation: fixtures use `MealOffSettings` / `OrderWalletSettings`; assert against helpers.
- **[Risk] Conflict with exclude-low-balance kitchen change** → Mitigation: no change to blocked exclusion math; this change only ensures unblock does not revive past-cutoff slots.

## Migration Plan

1. Deploy code only (expected: no schema migration).
2. No data backfill required for correctness going forward; optional ops note if a same-day late resume already inflated live counts before deploy (manual skip those deliveries if needed).
3. Rollback: revert the resume helper; worst case returns to pre-fix late-reactivation behavior (no irreversible schema).

## Open Questions

- None blocking implementation: reuse `CUTOFF_PASSED_NOTE` vs a more specific note token (`low_balance_resume_cutoff_passed`) can be chosen during apply for support clarity; kitchen behavior is identical either way.
