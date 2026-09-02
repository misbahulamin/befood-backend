## Why

Admin kitchen page (`/admin/kitchen/today`) already shows lean headcount and ingredient kg totals, while package-wise demand lives on a separate Meal Demand page. Kitchen staff and admins need one structured cooking summary — package-wise meal counts plus cross-package item consolidation — with filters and a printable one-page sheet. Splitting that across two screens without print support slows daily prep and invites miscounts.

## What Changes

- **Unified kitchen order summary API**: One admin read endpoint (or an additive extension of the existing kitchen today-requirement response) that returns, for a filtered `(service_date, meal_period[, package])`:
  - Package-wise summary (`total_customers` / final cooking meals per package)
  - Item-wise cooking calculation (ingredients aggregated across packages) with optional per-package contribution breakdown (e.g. Dal = Student 10 + Regular 3 → 13)
  - Existing confirmation status, expected / meal-off / final totals, and incomplete-menu flags
- **Aligned filtering**: Date, meal period (`lunch`/`dinner`), and package (`package_public_id`) on the summary surface; reuse existing meal-demand filter semantics. Do **not** add `meal_type` (daily/weekly/…) as a primary kitchen filter unless analysis proves a concrete kitchen need — packages already isolate plans.
- **Admin dashboard enhancement** (`befood-frontend` `/admin/kitchen/today`): Package-wise summary section + item-wise consolidated cooking section on the same page; filter controls that drive both the on-screen data and the printable sheet.
- **Printable sheet**: Generate a clean, kitchen-readable, preferably one-page PDF/print layout from the same filtered summary payload (Section 1 package summary, Section 2 item-wise calculation, Section 3 optional prep notes such as confirmation status / incomplete menu warnings). Prefer client-side print/PDF from the API JSON first; avoid inventing a separate report backend unless signed download or automation is required later.
- **Reuse-first**: Calculations stay in `orders.services.meal_demand` (`get_demand`, `get_ingredient_requirements`, `build_kitchen_requirement`). No new demand domain models. No **BREAKING** removals of existing meal-statistics or kitchen lean fields — additive enrichment only.
- **Docs + tests**: Backend OpenAPI/docs and frontend admin kitchen docs; API and UI tests for filters, aggregation, and auth.

## Capabilities

### New Capabilities

- `kitchen-order-summary`: Admin kitchen order summary contract — package-wise meal summary, item-wise cross-package cooking calculation with contribution breakdown, filter alignment, and printable sheet data shape for a service date / meal period.
- `kitchen-order-summary-frontend`: Admin Kitchen Today dashboard UI (package + item sections), filter UX, and printable/PDF sheet generation from the summary payload.

### Modified Capabilities

- `kitchen-cooking-requirement`: Extend the lean kitchen today-requirement API with package-wise rows and `package_public_id` filter; enrich ingredient rows with cross-package headcount / contribution detail needed for the cooking sheet without removing existing lean fields.

## Impact

- **Backend (`befood-backend`)**: `orders/services/meal_demand.py`, `orders/api/views.py` (`KitchenTodayMealRequirementView` and/or a thin summary view), serializers, OpenAPI, `orders/docs/`, tests under `orders/tests/`
- **Existing reuse**: `get_demand` / `demand_to_dict` (package rows), `get_ingredient_requirements` (cross-package ingredient aggregation), meal-off confirmation rules, published `MonthlyMenuSlotItem` → `Ingredient` resolution
- **Frontend (`befood-frontend`)**: `AdminKitchenTodayPage.tsx`, `adminMealDemandApi.ts`, `useAdminMealDemand.ts`, meal-demand types; optional shared print stylesheet/component. Sibling Meal Demand page remains; Kitchen Today becomes the cooking-sheet surface (may deep-link or reuse filter patterns from Meal Demand).
- **Auth**: Verified admin only (`IsVerifiedAdmin`); no customer-facing exposure.
- **Out of scope**: New dish/plate models, inventory purchasing integration, changing meal-off business rules, backend PDF microservices (unless print CSS proves insufficient), deliveryman or customer apps.
- **Cross-repo note**: OpenSpec lives in `befood-backend`; frontend tasks are implemented in `F:\befood\befood-frontend` and documented under the frontend capability.
