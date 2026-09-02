## Context

Admin kitchen prep today is split across two surfaces:

| Surface | API | Shows |
|---------|-----|--------|
| `/admin/meal-demand` | `GET /orders/meal-statistics/` | Package-wise expected / meal-off / final counts |
| `/admin/kitchen/today` | `GET /orders/kitchen/today-meal-requirement/` | Lean totals + aggregated ingredient kg |

Domain math already lives in `orders.services.meal_demand`:

- **Package** = `MealCategory` (`meal_name`, `public_id`)
- **Demand unit** = live `OrderDelivery` for `(service_date, meal_period)` via `live_delivery_q()`
- **Day’s food items** = published `MonthlyMenuSlotItem` → `Ingredient` (no separate Dish model)
- **Item aggregation** = same ingredient across packages summed by `final_cooking_count`

Kitchen Today does **not** return `packages[]`, does **not** accept `package_public_id`, and ingredient rows do **not** expose per-package headcount contribution (e.g. Dal: Student 10 + Regular 3 → 13 people). There is no printable sheet.

Stakeholders: kitchen staff (print/read sheet), admins (dashboard filters), backend maintainers (reuse meal_demand, no duplicate domain).

Constraints: follow existing DRF service-layer patterns; additive API only; OpenSpec repo-local to `befood-backend` while frontend ships in `befood-frontend`.

## Goals / Non-Goals

**Goals:**

- One filtered payload that powers both the enhanced Kitchen Today dashboard and a printable sheet
- Package-wise meal summary (customers + final cooking meals per package)
- Item-wise cooking calculation with cross-package **headcount** consolidation and per-package contribution; keep existing kg quantities when yield data exists
- Filters: `service_date`, `meal_period`, `package_public_id` (aligned with meal-statistics)
- Printable, preferably one-page, kitchen-readable sheet from the same data
- Preserve existing lean kitchen and meal-statistics clients (additive fields / optional filter only)

**Non-Goals:**

- New dish/plate models or renaming Ingredient → “menu item” in the DB
- Primary kitchen filter by `meal_type` (daily/weekly/monthly) in v1
- Customer name lists on the sheet (counts only; today-board remains for row-level ops)
- Changing meal-off deadlines, snapshot freezing, or inventory purchasing
- Mandatory server-side PDF binary generation in v1 (client print/PDF from JSON is the default)
- Merging Meal Demand analytics page into Kitchen Today (Meal Demand can stay for multi-period analytics)

## Decisions

### 1. Extend kitchen today-requirement instead of a second summary URL

**Choice:** Enrich `build_kitchen_requirement` + `KitchenTodayMealRequirementView` (same path: `/orders/kitchen/today-meal-requirement/` and web alias).

**Rationale:** Kitchen Today is already the cook-facing page; one round-trip for dashboard + print; meal-statistics remains for period-array analytics. Avoids dual sources of truth.

**Alternatives considered:**

- New `GET /orders/kitchen/order-summary/` — clearer name, but duplicates defaults/auth/docs; deferred unless lean clients cannot tolerate additive fields.
- Frontend composes meal-statistics + kitchen today — two requests, filter drift risk, harder print consistency.

### 2. Additive response shape

```text
existing lean fields
+ packages[]          # same shape as meal-statistics package rows
+ ingredients[].package_contributions[]
+ ingredients[].customer_count   # sum of contributing package final_cooking_count
```

`package_contributions` entry: `{ package_public_id, package_name, customer_count }` where `customer_count` is that package’s `final_cooking_count` when the published slot includes the ingredient.

**Rationale:** Matches product language (“13 জন”) while keeping kg for purchasing. Existing clients ignore unknown fields.

### 3. Enrich aggregation inside `get_ingredient_requirements`

**Choice:** Extend the existing aggregate loop to track per-package headcount contributions when building each ingredient entry; expose via `ingredient_qty_to_dict`.

**Rationale:** Same published-slot resolution path; snapshot freeze (`_freeze_ingredients`) can omit contributions or store them optionally later — history consumers do not need the sheet breakdown in v1. Prefer not to change snapshot schema unless product asks.

**Alternative:** Separate `get_item_wise_cooking_summary(demand)` — clearer separation but duplicates slot iteration; only if the function becomes unreadable.

### 4. Package filter on kitchen endpoint

**Choice:** Pass optional `package_public_id` into `get_demand` (already supported) from the kitchen view; invalidate with `400` on bad UUID the same way statistics does.

**Rationale:** Filtered dashboard and print share one query path.

### 5. Print / PDF on the frontend

**Choice:** v1 = print-optimized view (CSS `@media print` and/or a small PDF library already acceptable in the frontend stack) driven by the same React state as the dashboard. Filename example: `kitchen-summary-{date}-{period}.pdf`.

**Rationale:** No new backend dependency; sheet always matches on-screen filters; faster iteration on layout. Revisit server PDF only if ops need signed URLs, email attachment, or non-browser generation.

**Sheet sections:**

1. Header: date, meal period, confirmation status, overall final count  
2. Package-wise summary table  
3. Item-wise table: name, customer_count, contributions, optional kg  
4. Footer notes: `ingredients_incomplete` warning if true  

Target: fit one A4 page for typical package/item counts; allow overflow only when many packages/items.

### 6. Frontend page strategy

**Choice:** Enhance `AdminKitchenTodayPage` with package summary + item contribution UI + filter bar (date, period, package) + Print/Download. Reuse types/hooks from meal-demand API module; optionally share filter component patterns with `AdminMealDemandPage`.

**Rationale:** Product URL already points at `/admin/kitchen/today`; avoids forcing staff onto Meal Demand for cooking sheets.

### 7. Glossary for docs/UI copy

| Product language | Implementation |
|------------------|----------------|
| Package | `MealCategory` |
| Meal / customer count for cook | `final_cooking_count` (after meal-off) |
| Food item | `Ingredient` on published slot |
| Meal type filter | Out of scope v1; use meal **period** (`lunch`/`dinner`) |

## Risks / Trade-offs

- **[Risk]** Additive kitchen payload slightly larger for mobile-unaware clients → **Mitigation:** Web admin only; packages list is small (few MealCategories); contributions are compact.
- **[Risk]** Incomplete published menus → empty/partial items while package counts remain → **Mitigation:** Keep `ingredients_incomplete`; surface warning on dashboard and print section 3.
- **[Risk]** “Item” confusion (dish vs ingredient) → **Mitigation:** Document Ingredient = cooking line item; UI labels “Item” / ingredient name consistently.
- **[Risk]** One-page PDF fails with large menus → **Mitigation:** Compact typography; multi-page fallback acceptable; do not truncate counts.
- **[Risk]** Snapshot history omits contributions → **Mitigation:** Acceptable for v1; live endpoint is source for print; history unchanged.
- **[Trade-off]** No `meal_type` filter → packages already partition plans; add later if ops prove need.

## Migration Plan

1. Ship backend additive fields + `package_public_id` on kitchen endpoint (backward compatible).
2. Deploy frontend Kitchen Today enhancement + print; old UI still works against new API.
3. Update `orders/docs/backend` and `orders/docs/frontend` meal-demand/kitchen docs.
4. Rollback: revert frontend first; backend additive fields are harmless if left deployed.

## Open Questions

- Confirm product copy: show `expected` / `meal_off` beside final on package cards, or final-only on the sheet? (Default: dashboard shows all three; print emphasizes final + contributions.)
- Prefer browser Print dialog vs dedicated PDF download button, or both? (Default: both — Print opens dialog; Download PDF if a lightweight client library is already in the frontend, else Print-to-PDF guidance.)
- Should filtered package mode hide zero-contribution packages from the package section? (Default: yes — only packages in the filtered demand result.)
