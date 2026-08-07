## Context

Befood already has:

- **Order deliveries** per `(service_date, meal_period)` with statuses including `scheduled` and `skipped` (`skip_source` customer/admin)
- **Meal-off / meal-on** gated by configurable deadlines (Asia/Dhaka by default; lunch = D−1 lunch off time; dinner = D dinner off time)
- **Packages** with `meal_period` (`lunch` / `dinner` / `both`) and monthly (and other) subscriptions generating period-aware slots
- **Monthly menu schedules** assigning plan ingredients to concrete `(service_date, meal_period)` slots per package
- **Ingredient catalog** with optional `customers_per_kg` (kg yield) and flat `cost_per_customer` (money, not physical qty)

Kitchen still lacks a first-class **demand + ingredient requirement** view: operators infer headcount manually, and meal-offs before deadline make future slots only estimates. Stakeholders: Admin (analytics / planning), Kitchen (today’s cook list), future analysts (history).

Constraints: reuse meal-off timezone/deadlines; keep customer APIs unchanged; money/quantity math must use `Decimal`; web admin routes under `/api/v1/web/...`; verified admin authorization patterns already used in `orders`.

## Goals / Non-Goals

**Goals:**

- Single shared service for expected / meal-off / final cooking counts + `estimated` | `confirmed`
- Package-wise and date/period-wise admin statistics
- Lean kitchen today-requirement API (headcount + ingredients)
- Ingredient kg totals from published slot menus × final counts (`1 / customers_per_kg`)
- Upserted historical snapshots after confirmation for analysis
- Clear estimated vs confirmed UX signals

**Non-Goals:**

- Changing customer meal-off/meal-on rules or wallet debit behavior
- Auto-purchasing inventory or stock deduction from permanent assets
- ML demand prediction (history only enables future work)
- Mobile-operator lean variants beyond admin/kitchen web APIs in v1
- Inventing kg quantities for flat-cost-only spices
- Replacing the existing kitchen delivery board (sibling capability, not a rewrite)

## Decisions

### 1. Source of truth for counts = `OrderDelivery` rows

**Choice:** Aggregate live deliveries for the date/period (exclude cancelled parent orders). Expected = all in-scope deliveries; meal-off = `status=skipped`; final = expected − skipped.

**Why:** Deliveries already encode package period, month lock, and meal-off. Avoid a parallel “subscriber count” table that can drift.

**Alternatives:** Count active subscriptions × calendar — rejected (misses daily packages, mid-month cancels, period snapshots).

### 2. One domain service, three API faces

**Choice:** `orders.services.meal_demand` (or `meals.services` + orders queries) exposes:

- `get_demand(service_date, meal_period, package_id=None) -> DemandResult`
- `get_ingredient_requirements(demand) -> list[IngredientQty]`
- `resolve_default_kitchen_slot(now) -> (date, period)`

APIs:

| Purpose | Suggested path |
|--------|----------------|
| Admin statistics | `GET /api/v1/web/orders/meal-statistics/` |
| Kitchen today requirement | `GET /api/v1/web/orders/kitchen/today-meal-requirement/` |
| Admin history | `GET /api/v1/web/orders/meal-history/` |

**Why:** Matches existing web orders mounting; kitchen board already lives under orders.

**Alternatives:** New `kitchen` Django app — deferred until more kitchen modules appear.

### 3. Estimated vs confirmed = meal-off deadline only

**Choice:** `confirmation_status` is purely deadline-based (reuse meal-off settings helpers). No separate “lock” button in v1.

**Why:** Business already defined finality as “after meal-off time ends.” Avoid dual locks.

### 4. Kitchen default period switch

**Choice:** In meal-off timezone: if local time `< dinner_off_time` → default `lunch`; else → default `dinner`. Documented; overridable via query params.

**Why:** Matches the product example (10:00 → lunch, afternoon → dinner) and reuses the same clock as dinner deadline without new settings in v1.

**Alternatives:** Separate `kitchen_period_switch_time` setting — optional later if ops need lunch prep after 14:00.

### 5. Ingredient quantity formula

**Choice:** For ingredients on the **published** monthly menu slot for each package:

- `kg_per_person = 1 / customers_per_kg` when kg pair present
- `total_kg = kg_per_person × final_cooking_count_for_package`
- Sum identical ingredients across packages by ingredient id

Flat-only ingredients: list with `quantity=null`, `quantity_available=false`.

**Why:** Catalog already stores yield as customers per kg; user’s 0.3 kg × 450 example is exactly `1/customers_per_kg`. Plan `servings_count` is month quota, not per-meal mass — do not use it as kg.

**Alternatives:** New `kg_per_serving` field — unnecessary if `customers_per_kg` is maintained.

### 6. History model = upsert snapshots

**Choice:** New model e.g. `MealDemandSnapshot` with unique `(service_date, meal_period, package_id)` (`package` nullable for overall rollup). JSON field for frozen ingredient lines. Writer: management command / Celery beat after deadlines, plus optional admin “refresh snapshot” for confirmed slots.

**Why:** Meets historical analysis without mutating past rows when catalog changes; prevents duplicate inserts.

**Alternatives:** Only event-source from delivery audit log — heavier and slower for kitchen reports.

### 7. Authorization

**Choice:** Same verified-admin gate as meal-off settings / kitchen board (`is_verified_admin`). No customer access.

### 8. Performance

**Choice:** Indexed aggregates on `OrderDelivery(service_date, meal_period, status)` with `select_related` order→meal. For a single day/period this is bounded by active subscribers (~hundreds–low thousands). No cache required in v1; add short TTL cache later if needed.

## Risks / Trade-offs

- **[Risk] Menu not published → empty ingredients while counts look fine** → Mitigation: response flag `ingredients_incomplete`; admin docs call out publish gate.
- **[Risk] Admin skip after “confirmed” changes live final count vs frozen history** → Mitigation: live APIs always reflect deliveries; history endpoints serve snapshots; document divergence; optional re-snapshot on admin skip.
- **[Risk] Misconfigured `customers_per_kg` → wrong kitchen kg** → Mitigation: show per-person kg in payload for audit; quantity_available false when missing.
- **[Risk] Default lunch/dinner switch wrong for late lunch prep** → Mitigation: query overrides; optional setting later.
- **[Trade-off] Overall rollup row vs sum-only** → Store package rows + compute overall on read to avoid double-write drift; optional overall snapshot for faster history lists.

## Migration Plan

1. Add `MealDemandSnapshot` (and indexes) via migration; no backfill required for go-live.
2. Ship read APIs (live demand) without waiting on history writer.
3. Add confirm-and-save command/job; optionally backfill last N confirmed days from current deliveries once.
4. Rollback: remove routes and stop job; snapshot table can remain unused.

## Open Questions

- Should deliveryman or a dedicated `KITCHEN` group access today-requirement, or admin-only in v1? **Default: verified admin only** (same as kitchen board) unless product requests a kitchen role.
- Persist estimated snapshots for mid-day dashboards? **Default: no** — only confirmed (and optional manual refresh of confirmed).
- Include `missed` / `delivered` in expected denominator? **Default: yes for expected** (they were cooking demand); meal-off remains `skipped` only — final cooking for *prep* dashboards may prefer “still to cook” subset; v1 final cooking = expected − skipped (business formula as specified), not “not yet delivered.”
