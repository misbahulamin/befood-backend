## Context

`CustomerProfile.meal_service_blocked_low_balance` marks customers whose spendable wallet balance fell below `meal_stop_threshold`. Auto meal delivery already excludes those deliveries via:

```python
.exclude(
    Q(subscription__customer__meal_service_blocked_low_balance=True)
    | Q(order__customer__meal_service_blocked_low_balance=True)
)
```

Kitchen planning uses a separate path: `orders/services/meal_demand.py` → `_demand_queryset` → `get_demand` / `build_kitchen_requirement` / `build_kitchen_order_details`. That queryset currently only applies `live_delivery_q` and optional package filters — it does **not** check the low-balance block. Result: kitchen counts and Order Details PDFs still include people who will not be cooked for / delivered.

Stakeholders: kitchen staff (cook headcount + print sheets), admin SPA Kitchen Today, ops relying on meal statistics / snapshots that share `get_demand`.

## Goals / Non-Goals

**Goals:**

- Align kitchen cook demand and Order Details eligibility with auto-delivery skip-on-block.
- Exclude blocked customers from **all** demand metrics derived from `_demand_queryset` (expected, meal-off, final, total_customers, package rows, ingredient kg, order-details rows).
- Keep response JSON structure identical (same keys/nesting); only values change when blocked customers exist.
- Single shared filter so admin statistics and kitchen stay consistent (`Deterministic single calculation path`).

**Non-Goals:**

- Changing how the block flag is set/cleared (cron, recharge approve resume).
- Adding a separate “blocked count” field or new API query param.
- Mutating delivery status when blocked (deliveries may remain `scheduled` / meal-on).
- Rewriting historical `MealDemandSnapshot` rows already persisted.
- Frontend UI redesign beyond documenting the eligibility rule.

## Decisions

### 1. Exclude at `_demand_queryset` (not only in views)

**Choice:** Add the same OR-exclude used by `eligible_delivery_queryset` inside `_demand_queryset`.

**Rationale:** Both kitchen APIs and `get_demand` (statistics, ingredients, snapshots) flow through this helper. One fix prevents kitchen vs statistics drift.

**Alternatives considered:**

- Filter only in `build_kitchen_*` views/helpers → rejects: statistics/snapshots diverge; duplicates logic.
- Treat blocked as synthetic meal-off (keep in expected, bump meal_off) → rejects: user wants no count/list at all; would mislabel wallet blocks as meal-offs.

### 2. Full exclusion vs final-only exclusion

**Choice:** Remove blocked customers from the queryset entirely so they contribute to neither expected nor meal-off nor the order-details list.

**Rationale:** Kitchen should not cook for them; listing or counting them as expected/off confuses ops. Matches “balance nei → no ranna, no name in list.”

### 3. Customer path matching

**Choice:** Exclude when `subscription__customer__meal_service_blocked_low_balance=True` **or** `order__customer__meal_service_blocked_low_balance=True`, mirroring auto delivery (subscription vs one-shot order parents).

**Rationale:** Demand already resolves customer via `Coalesce(subscription, order)`; both FK paths must be covered.

### 4. Response contract

**Choice:** No schema/field additions. Docs state that low-balance–blocked customers are omitted from live demand/kitchen payloads.

**Rationale:** User requirement: keep structure same-to-same.

### 5. Snapshots

**Choice:** New/upserted snapshots inherit exclusion via `get_demand`. Do not backfill old snapshots.

**Rationale:** History is freeze-at-capture; live kitchen is the operational truth going forward.

## Risks / Trade-offs

- [Admin statistics totals drop for blocked customers] → Mitigation: intentional; document in backend/frontend kitchen docs; same formula as kitchen.
- [Customer blocked mid-day after kitchen already printed] → Mitigation: live recalculation on next API refresh; no auto-reprint (ops process).
- [NULL customer edge cases on broken rows] → Mitigation: exclude only when related customer flag is True; False/default keeps inclusion (same as auto delivery).
- [Package with only blocked customers disappears from package list] → Mitigation: acceptable; empty packages simply omit from aggregation.

## Migration Plan

1. Implement exclude in `_demand_queryset` + tests.
2. Update kitchen/meal-demand docs.
3. Deploy; no DB migration.
4. Rollback: revert the queryset exclude (feature flag not required for this small change).

## Open Questions

None — product rule is clear: blocked ⇒ no kitchen count or list; response shape unchanged.
