## 1. Backend — order details menu enrichment

- [x] 1.1 In `orders/services/meal_demand.py`, extend `build_kitchen_order_details` to resolve published slot ingredient names per distinct package `meal_id` (cache per request) using `resolve_published_slot_for_delivery`, preserving slot item order
- [x] 1.2 Add `ingredient_names` and `menu_items_label` (`" + ".join(...)`) on each customer row; keep `name`, `phone`, `package_name`, `address`; empty list / empty-or-null label when menu missing
- [x] 1.3 Update kitchen order-details serializer + OpenAPI example/description on `KitchenTodayOrderDetails` / related view schema

## 2. Backend — tests and docs

- [x] 2.1 Add/update `orders/tests/test_meal_demand.py` cases: menu fields populated from published slot; empty menu fields when unpublished; existing identity fields and meal-off exclusion still hold
- [x] 2.2 Update `orders/docs/backend/meal-demand-kitchen-planning.md` and `orders/docs/frontend/meal-demand-kitchen-planning.md` for the enriched Order Details contract and Menu column guidance
- [x] 2.3 Run `python manage.py test orders.tests.test_meal_demand` and fix regressions

## 3. Frontend — Order Details Menu column

- [x] 3.1 Verify `KitchenOrderDetailsPreviewModal` and `KitchenOrderDetailsPrintSheet` use Menu (via `formatKitchenOrderDetailsMenuLabel`) and never fall back to `package_name`; polish table spacing/typography for a professional kitchen sheet
- [x] 3.2 Confirm types/API client accept `ingredient_names` / `menu_items_label`; extend `kitchenOrderDetailsPdf.test.ts` if needed for empty vs label cases
- [x] 3.3 Manually verify `/admin/kitchen/today` → Order Details preview + Download after backend deploy shows e.g. `mach + dhal + vat`

## 4. Frontend — Chef PDF columns

- [x] 4.1 Confirm `KitchenOrderSummaryPrintSheet` package table has only প্যাকেজ and চূড়ান্ত মিল (no প্রত্যাশিত / মিল অফ); leave আইটেম অনুযায়ী রান্না unchanged
- [x] 4.2 Keep on-screen Kitchen Today Expected / Meal off columns; add a short frontend doc note that Chef PDF omits those columns
- [x] 4.3 Smoke-test Chef Print/Download PDF against a multi-package slot
