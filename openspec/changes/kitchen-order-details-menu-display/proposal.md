## Why

Kitchen staff open Order Details to see who cooks for and what to cook per customer, but `GET /orders/kitchen/today-order-details/` only returns `package_name` — not that day’s published menu ingredients. The Admin SPA already expects menu fields (`menu_items_label` / `ingredient_names`) and falls back to `—`, so PDFs and the preview table look empty of food items. Separately, the Chef printable sheet must stay focused on final cook counts (প্যাকেজ + চূড়ান্ত মিল) without cluttering the download with প্রত্যাশিত / মিল অফ columns that belong on the on-screen dashboard only.

## What Changes

- **Enrich kitchen order-details API**: For each cooking customer row, resolve the published monthly menu slot for that customer’s package + `(service_date, meal_period)` and return today’s ingredient display names (plus a ready-to-render `menu_items_label` like `mach + dhal + vat`). Keep existing `name`, `phone`, `package_name`, `address` for compatibility (additive; not a **BREAKING** removal).
- **Missing menu handling**: When no published slot / empty items exist for that package-slot, return empty ingredient list and empty/null label (UI shows `—`); do not invent ingredients or fail the whole list.
- **Admin Order Details UI** (`befood-frontend` `/admin/kitchen/today` → Order Details): Show **Menu** (joined ingredients) instead of Package as the primary food column in the preview modal and print/PDF sheet; polish layout for kitchen readability.
- **Chef PDF / print sheet**: Ensure the Chef download shows only **প্যাকেজ** and **চূড়ান্ত মিল** in the package summary table — do **not** print প্রত্যাশিত or মিল অফ. Leave **আইটেম অনুযায়ী রান্না** unchanged. On-screen Kitchen Today may still show Expected / Meal off for ops.
- **Docs + tests**: Backend OpenAPI/docs/tests for the enriched contract; frontend docs/tests for Menu column + Chef PDF column set.

## Capabilities

### New Capabilities

- `kitchen-order-details-menu`: Per-customer cooking list contract for Order Details — today’s published menu ingredients / `menu_items_label` alongside identity and address fields.
- `kitchen-order-details-frontend`: Admin Kitchen Today Order Details preview + print/PDF showing Menu (ingredients) instead of Package; professional sheet polish.
- `kitchen-chef-print-columns`: Chef print/PDF package table column contract — প্যাকেজ + চূড়ান্ত মিল only; item-wise section unchanged.

### Modified Capabilities

- _(none)_ — existing `kitchen-cooking-requirement` aggregate math and lean ingredient kg fields stay as-is; this change only enriches order-details rows and print presentation.

## Impact

- **Backend (`befood-backend`)**: `orders/services/meal_demand.py` (`build_kitchen_order_details`), serializers/OpenAPI for `KitchenTodayOrderDetails`, `orders/docs/backend|frontend/meal-demand-kitchen-planning.md`, `orders/tests/test_meal_demand.py`. Reuse `resolve_published_slot_for_delivery` + slot items (same path as `get_ingredient_requirements`).
- **Frontend (`befood-frontend`)**: Order Details modal/print (`KitchenOrderDetailsPreviewModal`, `KitchenOrderDetailsPrintSheet`, `kitchenOrderDetailsPdf.ts` — already partially wired); Chef sheet (`KitchenOrderSummaryPrintSheet`) verified for column set; types in `mealDemandTypes.ts`; frontend docs if present.
- **Auth**: Verified admin only (unchanged).
- **Out of scope**: Changing aggregate kitchen requirement math, meal-off rules, item-wise contribution table, backend PDF microservice, customer-facing menu APIs.
