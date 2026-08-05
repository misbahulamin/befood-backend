## Context

Meal packages (`MealCategory`) already have a duration `meal_type` (`daily`, `weekly`, `half_monthly`, `monthly`, …). Cycle planning and costing assume every package needs `cycle_days × 2` main servings. Order delivery generation mostly follows the same two-slots-per-day rule (except daily, which is hardcoded to one lunch slot).

Product now needs an explicit **meal period** on each package: lunch only, dinner only, or both. Serving counts for the plan editor and fulfillment must be:

`service_days(meal_type, reference month) × periods_per_day(meal_period)`

where `periods_per_day` is `1` for `lunch`/`dinner` and `2` for `both`.

Stakeholders: verified admins (package create + plan editor), kitchen/ops (delivery slots), customers (per-meal price display).

## Goals / Non-Goals

**Goals:**

- Persist `meal_period` on `MealCategory` and require it on admin create/update APIs.
- Centralize expected-serving math shared by plan finalize, costing, public per-meal price, and order slot generation.
- Make plan summary expose `expected_servings` / `main_servings_expected` from the linked package + cycle month (not always cycle `total_meals`).
- Align order delivery slots with the package period (snapshot period on the order when needed).
- Migrate existing packages to `both` so current `× 2` behavior is preserved.

**Non-Goals:**

- Redesigning the monthly kitchen menu calendar to be package-specific (menu schedule can still plan lunch + dinner for the kitchen).
- Changing meal_type duration definitions (reuse `calculate_order_period` day counts).
- Per-day custom lunch/dinner toggles inside a single package (package-level choice only).
- Customer self-service choosing lunch vs dinner at checkout (admin defines the package).

## Decisions

### 1. Field: `MealCategory.meal_period`

Add `meal_period` with choices `lunch` | `dinner` | `both`, required on create/update.

**Why:** Matches existing `MealPeriod` language on menu slots and order deliveries; one field is enough for product rules.

**Alternatives:** Two booleans (`includes_lunch`, `includes_dinner`) — more flexible but allows invalid “neither”; rejected for simplicity. Separate SKUs per period without a field — rejected (duplicates packages and breaks shared costing).

### 2. Shared helpers in `meals/services/pricing.py` (or small `serving_counts.py`)

- `periods_per_day(meal_period) -> 1 | 2`
- `service_days_for_meal_type(meal_type, year, month) -> int`  
  Reuse order-duration rules against the cycle (or present) month:
  - daily → 1  
  - weekly → 7  
  - half_monthly → 15  
  - monthly → `get_month_days(year, month)`  
  - six_months / yearly → inclusive day count from the 1st of that month using the same add-months logic as orders (document the reference anchor as cycle month start for planning)
- `expected_servings(meal_type, meal_period, year, month) -> int`  
  = `service_days × periods_per_day`

**Why:** One formula for plan editor, pricing, and orders avoids drift.

### 3. Cycle `total_meals` stays calendar max (`cycle_days × 2`)

Keep `MealCycle.total_meals = cycle_days × 2` as the kitchen calendar capacity indicator.

**Plan-level target** becomes `expected_servings(package.meal_type, package.meal_period, cycle.year, cycle.month)`.

Finalize validation and `per_meal_rate` use the plan expected servings. Summary responses MUST include `expected_servings` (and keep showing cycle `total_meals` for context).

**Why:** Different packages in the same cycle can differ (monthly both = 60 vs monthly dinner = 30 vs daily both = 2). A single cycle total cannot be the finalize target for every plan.

**Alternatives:** Remove cycle `total_meals` — breaking for existing clients; deferred. Store expected servings on `MealCyclePlan` at create time — useful cache, but always recompute from package + cycle to avoid stale values when package period changes before finalize.

### 4. Snapshot `meal_period` on orders

When creating an order, persist `meal_period_snapshot` (mirror of `meal_type_snapshot`) from the package at purchase time. Delivery generation reads the snapshot so later package edits do not rewrite historical orders.

**Why:** Same pattern as meal type / price snapshots.

### 5. Order slot generation

| meal_period | slots per service day |
|-------------|------------------------|
| `lunch` | lunch only |
| `dinner` | dinner only |
| `both` | lunch + dinner |

Daily + `both` → 2 slots on the service day; daily + single period → 1 slot of that period (replace today’s hardcoded lunch-only for all daily packages).

### 6. Public `per_meal_price`

`per_meal_price = total_price / expected_servings(meal_type, meal_period, present_year, present_month)` (quantize to money rules). Stop hardcoding `days × 2` in `calculate_per_meal_price`.

### 7. Changing `meal_period` after plans exist

Allow update while package is not locked by a finalized plan **or** allow update but require reopen + re-finalize for affected plans. Preferred: allow field update; draft plans pick up new expected servings automatically; finalized plans keep snapshot costs until reopen (same as price edits). Document that admins should reopen plans after changing period.

## Risks / Trade-offs

- **[Risk] Existing daily orders assumed 1 lunch slot; daily + both becomes 2** → Mitigation: default migration `both` only for packages; new daily+both is intentional. Existing open daily orders keep lunch-only via snapshot default `lunch` if we backfill snapshots carefully—for historical orders without snapshot, treat missing snapshot as `lunch` for daily and `both` for multi-day (preserve prior behavior).
- **[Risk] six_months/yearly planning day counts are large** → Mitigation: reuse existing order duration math; no new unbounded behavior beyond current slot generation risks.
- **[Risk] Clients break on required `meal_period`** → Mitigation: OpenAPI + docs; clear 422; migration defaults existing rows to `both`.
- **[Trade-off] Menu schedule still lunch+dinner every day** → Kitchen calendar remains full; package period only affects package economics and customer fulfillment. Acceptable until product asks for period-filtered menus.

## Migration Plan

1. Add nullable `meal_period`, backfill `both`, then set non-null with default `both`.
2. Add `Order.meal_period_snapshot` nullable → backfill from package when available, else `both` (multi-day) / `lunch` (daily), then set non-null for new orders.
3. Deploy API requiring `meal_period` on create/update.
4. Update plan finalize/summary/costing and delivery generation in the same release.
5. Rollback: field remains with default `both`; code can temporarily ignore period if needed (not preferred).

## Open Questions

- Should weekly/half_monthly packages that choose a single period still run every calendar day in the window (yes per current design)?
- For six_months/yearly cycle planning, is “anchor = 1st of cycle month for duration math” acceptable, or should planning only be supported for `monthly`/`daily`/`weekly`/`half_monthly` packages in a cycle?
