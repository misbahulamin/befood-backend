## Context

BeFood prices each cook-day lunch/dinner slot with the one-meal formula already used by `build_one_meal_price_preview` and publish-time `slot_pricing`:

```text
profit = ingredient_cost × profit_percent / 100
final_price = ingredient_cost + operational_cost + profit
```

Subscriber paths use `MealCyclePlan.profit_percent` and lock results onto `MonthlyMenuSlot` snapshots at publish (`final_meal_price_snapshot`, `ingredient_cost_snapshot`, `operational_cost_snapshot`, `profit_snapshot`). Instant Meal cards already re-apply the same formula with `InstantMealSettings.profit_percent` without mutating those snapshots.

Admin schedule detail (`MonthlyMenuScheduleSerializer` → `serialize_schedule_assignments`) currently exposes only `final_meal_price` for the admin published-menus page. Operators cannot see ingredient cost, Instant ladder, or profits without leaving the page or trusting frontend math.

Constraints:

- Additive API only — keep existing `final_meal_price` / `price` semantics for subscribers.
- Do not change wallet debit or subscription billing.
- Instant `profit_percent` changes must refresh Instant display prices without rewriting subscriber snapshots.
- Decimal money quantization must stay consistent with `cycle_calculations` (`MONEY_PLACES`).

## Goals / Non-Goals

**Goals:**

- Single shared pure function for one-meal price math reused by cost-preview, publish snapshotting, Instant cards, and admin published-menu dual pricing.
- Admin published/schedule detail returns per-slot cost + subscriber + Instant pricing ladders from the backend.
- Instant settings remain the sole Instant profit source (no hardcoding).
- Tests and docs cover calculation parity and non-breaking response shape.

**Non-Goals:**

- Instant order, payment, or delivery (still out of Instant offering scope).
- Changing locked subscriber snapshot values after Instant settings change.
- Frontend implementation in this repo (document the contract only; admin UI lives elsewhere).
- New DB tables or Instant Meal persistence.
- Breaking rename/removal of `final_meal_price` or Instant list fields.

## Decisions

### 1. Shared pricing helper location

**Decision:** Add `meals/services/pricing.py` with `calculate_meal_price(ingredient_cost, operational_cost, profit_percent)` returning quantized string/Decimal fields (`ingredient_cost`, `profit_percent`, `profit_amount`, `final_price`, and optionally echo `operational_cost`). Refactor `build_one_meal_price_preview` and Instant snapshot-based branch to call it for the arithmetic core.

**Alternatives considered:**

- Keep duplicating formula in `instant_meals.py` / `cycle_calculations.py` — rejected (rounding drift risk).
- Only refactor Instant to call `build_one_meal_price_preview` — insufficient; admin dual pricing and future invoice/report need a named, ingredient-agnostic helper when costs already exist as snapshots.

### 2. Cost basis on published admin detail

**Decision:** For **published** slots, prefer publish snapshots for `selected_ingredients_cost` / ingredient cost and `operational_cost`. Subscriber ladder uses snapshot final price + snapshot profit + plan/snapshot profit percent. Instant ladder = `calculate_meal_price(snapshot_ingredient_cost, snapshot_or_resolved_op_cost, InstantMealSettings.profit_percent)`.

Align with existing Instant card logic: if ingredient snapshot exists, use it; otherwise live preview from assigned ingredients + resolved op cost.

**Alternatives considered:**

- Always recompute live catalog costs on admin detail — rejected for published menus (would diverge from locked subscriber charge and Instant cards that prefer snapshots).
- Persist Instant price on the slot — rejected (Instant % is global/live; proposal requires settings refresh without republish).

### 3. Response shape (additive)

**Decision:** Extend each admin assignment entry with:

```json
{
  "service_date": "2026-09-01",
  "meal_period": "lunch",
  "ingredients": [...],
  "final_meal_price": "59.24",
  "selected_ingredients_cost": "48.15",
  "operational_cost": "4.13",
  "subscriber_pricing": {
    "profit_percent": "14.45",
    "profit_amount": "6.96",
    "final_price": "59.24"
  },
  "instant_pricing": {
    "profit_percent": "70.00",
    "profit_amount": "33.70",
    "final_price": "85.98"
  },
  "subscriber_price": "59.24",
  "instant_price": "85.98"
}
```

- Keep `final_meal_price` as today (subscriber).
- Add nested `subscriber_pricing` / `instant_pricing` for rich UI.
- Add flat `subscriber_price` / `instant_price` aliases for simple table columns.
- Draft slots without snapshots: null pricing fields or live preview only where already safe; do not invent zeros.

**Alternatives considered:**

- Replace `final_meal_price` with nested-only — **BREAKING**, rejected.
- Frontend-only Instant calc — rejected (rounding / rule drift).

### 4. Where Instant settings are loaded

**Decision:** Load `InstantMealSettings.load()` once per schedule serialize (or request), pass `profit_percent` into assignment serialization. Do not N+1 settings reads per slot.

### 5. Scope of refactor

**Decision:** Phase 1 wires shared helper + admin schedule dual fields + tests/docs. Instant list continues to work; migrate its arithmetic onto the helper in the same change when low-risk. Do not touch `orders` wallet payment paths.

## Risks / Trade-offs

- **[Risk] Response payload grows for full-month schedules** → Mitigation: fields are small decimals; no nested Instant catalogs; keep customer-visible serializers without dual pricing.
- **[Risk] Draft vs published inconsistency** → Mitigation: document null vs live preview rules; dual Instant ladder primarily guaranteed for published slots with cost snapshots.
- **[Risk] Accidental subscriber snapshot mutation** → Mitigation: Instant path remains read-only; tests assert snapshots unchanged after Instant % PATCH.
- **[Risk] Naming confusion (`price` vs `final_meal_price` vs `subscriber_price`)** → Mitigation: OpenAPI + frontend doc map aliases; `final_meal_price` remains canonical subscriber field on schedule assignments.
- **[Trade-off] Instant price not frozen at publish** → Accepted: Instant margin is settings-driven and intentionally live for display/cards.

## Migration Plan

1. Land shared `calculate_meal_price` + unit tests (subscriber/instant examples from proposal).
2. Enrich `serialize_schedule_assignments` (admin path) and OpenAPI/serializers.
3. Point Instant / cost-preview arithmetic at the helper without changing public Instant card field names.
4. Deploy backend; existing clients ignore new fields.
5. Frontend admin published-menus page switches to new columns (separate deploy).
6. Rollback: revert API enrichment; subscriber billing unaffected.

## Open Questions

- Exact frontend route `/admin/published-menus/{menu_id}` may map to schedule `public_id` or numeric id — confirm lookup field when applying; contract is schedule detail assignments enrichment either way.
- Whether draft admin detail should show live dual pricing before publish (nice-to-have; default null Instant/subscriber ladders until snapshots exist unless live preview is already shown).
