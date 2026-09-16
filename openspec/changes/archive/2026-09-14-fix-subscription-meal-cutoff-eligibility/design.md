## Context

BeFood subscription meal service creates rolling `OrderDelivery` rows via `ensure_subscription_deliveries` when a customer subscribes (and again from retrieve/current and the rolling ensure cron). Auto-delivery cron selects deliveries with `status=scheduled` for a `(service_date, meal_period)` and marks them delivered, which debits the wallet.

Meal cutoff times live on the singleton `MealOffSettings` (`timezone`, `lunch_off_time`, `dinner_off_time`), exposed at `/orders/meal-off-settings/` and `/api/v1/web/orders/meal-off-settings/`. Deadline math already exists in `orders/services/meal_off.py` (`meal_off_deadline`, `meal_off_business_now`) and gates **customer meal-off/on only**. Slot generation never consults those helpers, so a subscribe after lunch cutoff still inserts today's lunch as `scheduled`.

**Root-cause verdict (analysis):** Cron and wallet deduction are behaving as designed. The defect is upstream: new slots are always created `scheduled`. Fix belongs in the generation layer.

**Current create path:**

```text
POST /api/v1/subscriptions/
  → SubscribeSerializer.create
  → subscribe_customer()
  → ensure_subscription_deliveries()  # always status=SCHEDULED
```

## Goals / Non-Goals

**Goals:**

- When creating a new subscription delivery slot, decide `scheduled` vs `skipped` using meal-off settings + current business time in the settings timezone (default Asia/Dhaka).
- Preserve auditability: skipped-for-cutoff rows exist with `skip_source=system` and a stable `note` token `cutoff_passed`.
- Keep auto-delivery and wallet charge paths untouched so existing healthy subscribers keep working.
- Cover lunch/dinner before/after cutoff and timezone comparison with tests.

**Non-Goals:**

- Changing cron eligibility, mark-delivered, or wallet debit rules.
- Backfilling or mutating existing `OrderDelivery` rows already stored as incorrectly `scheduled`.
- Changing meal-off/on customer APIs or meal-off settings contract.
- Hardcoding 02:00 / 16:00 in application code.
- Adding a dedicated `skip_reason` DB column in v1 (use `note` + `skip_source`).
- Changing kitchen demand formulas beyond the natural effect of more `skipped` rows for post-cutoff new subscribers.

## Decisions

### 1. Fix only in `ensure_subscription_deliveries` (single choke point)

**Choice:** Apply cutoff eligibility inside `ensure_subscription_deliveries` when constructing each new `OrderDelivery`, before `bulk_create`.

**Rationale:** Subscribe, API ensure-on-read, and the rolling ensure management command all share this function. One change covers every new slot. Cron remains status-driven.

**Alternatives considered:**

- Patch only `subscribe_customer` — misses rolling ensure creating a first-day slot late.
- Teach auto-delivery to re-check cutoff — would change production cron semantics for all users and risk skipping legitimately scheduled meals; rejected per product rules.
- Soft-delete / omit the row entirely — loses audit/support visibility; rejected.

### 2. Reuse existing meal-off deadline helpers; optional thin predicate

**Choice:** Call `get_meal_off_settings()`, `meal_off_business_now()`, and `meal_off_deadline(service_date, meal_period, settings)`. Skip when `now > deadline` (same boundary as meal-off: at-or-before deadline remains allowed / `scheduled`). Optionally add `is_past_meal_cutoff(...)` in `meal_off.py` for clarity and tests.

**Rationale:** Same-day cutoff math was aligned in `align-meal-off-cutoff-same-day`; subscription generation must share that source of truth.

### 3. Audit fields without migration

**Choice:**

| Field | Value when cutoff already passed |
| --- | --- |
| `status` | `skipped` |
| `skip_source` | `system` |
| `note` | stable token including `cutoff_passed` (e.g. `cutoff_passed`) |
| `marked_at` | `timezone.now()` (optional but useful for support) |

**Rationale:** Matches cancel-future-slot pattern (`skipped` + `system`). No schema migration → safest production deploy. Customer meal-on remains blocked for non-`customer` skip sources, so system cutoff skips stay locked.

**Alternatives considered:** New `skip_reason` enum/column — clearer long-term, but requires migration and serializer/docs churn; defer unless product insists.

### 4. Scope of dates evaluated

**Choice:** Evaluate cutoff for **every newly created** slot using `(service_date, meal_period)` vs `now`. In practice only **today's** periods can be past cutoff; future dates remain `scheduled`. Past dates are not generated (`start = max(started_on, today)`).

**Rationale:** Matches business cases (post-lunch-cutoff subscribe → lunch skipped, dinner still scheduled if dinner cutoff not passed).

### 5. Idempotency unchanged for existing rows

**Choice:** If a `(service_date, meal_period)` already exists, do not update it. Cutoff logic applies only to rows about to be created.

**Rationale:** Production-safe; avoids rewriting live schedules. Pre-deploy bad rows need a separate ops playbook if required.

### 6. Boundary semantics

**Choice:** Mirror meal-off: eligible (`scheduled`) while `business_now <= deadline`; past cutoff when `business_now > deadline`.

**Rationale:** Subscribe at 01:59 with lunch cutoff 02:00 → lunch scheduled; at 02:01 → lunch skipped. Aligns tests and meal-off UX.

## Risks / Trade-offs

- **[Risk] Pre-existing incorrectly scheduled same-day slots still charge after deploy** → Mitigation: document forward-only fix; optional one-off ops query out of scope; do not auto-mutate production rows in this change.
- **[Risk] Rolling ensure creates today's missing slot after cutoff as skipped (good) but never "upgrades" a wrongly scheduled row** → Mitigation: accept; only new creates are fixed.
- **[Risk] Demand / kitchen counts include extra system skips for late subscribers** → Mitigation: correct business outcome (should not cook those meals); no formula change needed.
- **[Risk] `note` free-text is weaker than a typed reason** → Mitigation: use exact stable token `cutoff_passed`; add typed column later if needed.
- **[Risk] Timezone mistakes if code uses UTC `date.today()`** → Mitigation: continue using `business_today()` / `meal_off_business_now()` from meal-off settings TZ only.

## Migration Plan

1. Deploy code + tests (no DB migration).
2. Smoke: subscribe after lunch cutoff with published menu → today's lunch `skipped`/`system`/`cutoff_passed`, dinner `scheduled` if before dinner cutoff.
3. Confirm lunch auto-delivery run does not select that skipped lunch; dinner still eligible when scheduled.
4. Rollback: revert the generation commit; existing post-fix skipped rows remain skipped (safe); new subscribers after rollback regain pre-fix over-scheduling behavior.

## Open Questions

- None blocking implementation. Optional later: dedicated `skip_reason` field and/or one-off remediation script for historical same-day overcharges — product/ops decision outside this change.
