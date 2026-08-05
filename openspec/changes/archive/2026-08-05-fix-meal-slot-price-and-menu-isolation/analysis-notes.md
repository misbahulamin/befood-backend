# Analysis notes (tasks 1.1–1.2)

## 1.1 Average-rate call sites

| Location | Field / behavior | Role after this change |
|----------|------------------|-------------------------|
| `orders/services/meal_payment.py` | Was `Order.per_meal_price_snapshot` | **Fixed:** uses published slot `final_meal_price_snapshot` |
| `orders/services/order_service.prepare_snapshot_fields` | Sets `per_meal_price_snapshot` at order create | Kept for eligibility / package estimate |
| `meals/services/meal_offering.resolve_public_per_meal_price` | `snapshot_per_meal_rate` or total÷servings | Public estimate display |
| `meals/services/cycle_calculations.calculate_package_totals` | `per_meal_rate` | Package rollup reference |
| Order eligibility min balance | Uses average × meals | Unchanged (follow-up) |

## 1.2 Multi-package mutation paths

| Path | Scope | Risk |
|------|-------|------|
| `publish_schedule` / `unpublish_schedule` | Single schedule PK via `select_for_update` | OK — package isolated |
| `replace_schedule_assignments` | Deletes only `schedule.slots` | OK |
| `apply_sync_suggestion` | Calls `replace_schedule_assignments(target, …)` only | OK — source untouched |
| `reopen_plan` | Deletes draft schedule on **that** plan only | OK — siblings untouched |
| Schedule delete ViewSet | Object-level destroy | OK |
| List filters | Must include meal_category + cycle | Verified; no global one-per-month collapse |

Likely “menu disappeared” causes: frontend cache keyed by month only, or explicit sync/delete of wrong schedule — not publish cascade.
