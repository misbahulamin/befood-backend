## 1. Meal pricing model & admin create

- [x] 1.1 Make `MealCategory.total_price` nullable; migrate existing rows unchanged
- [x] 1.2 Update admin meal create/update serializers so `total_price` is not required/writable for publishing
- [x] 1.3 Expose read-only `pricing_status` (`priced`/`unpriced`) on meal serializers
- [x] 1.4 Update meal admin + seed/tests that assumed required `total_price` on create

## 2. Finalize publishes meal price

- [x] 2.1 Extend `finalize_plan` to set linked meal `total_price = snapshot_total_cost` in the same transaction
- [x] 2.2 Ensure failed finalize (main-servings mismatch) does not change meal price
- [x] 2.3 Confirm `reopen_plan` clears plan snapshots but keeps meal `total_price`
- [x] 2.4 Include published meal price fields in finalize summary response

## 3. Public meal offering API

- [x] 3.1 Add service to resolve latest finalized plan for a meal (year/month/finalized_at order)
- [x] 3.2 Build customer-safe `current_cycle_offering` payload (cycle meta, snapshot bands, menu servings; no kg unit prices)
- [x] 3.3 Enrich public meal list/detail serializers with pricing status + offering on detail
- [x] 3.4 Update OpenAPI tags/examples for public meal detail

## 4. Orders & safety

- [x] 4.1 Reject order create when meal `total_price` is null
- [x] 4.2 Add/adjust order tests for unpriced meal rejection

## 5. Tests

- [x] 5.1 Admin can create meal without `total_price`
- [x] 5.2 Finalize updates meal price; mismatch leaves price unchanged
- [x] 5.3 Reopen keeps published meal price
- [x] 5.4 Public detail returns offering; omits supplier unit prices
- [x] 5.5 Public list shows priced vs unpriced correctly

## 6. Documentation

- [x] 6.1 Update `meals/docs/backend/meal-cycle-management.md` with publish-on-finalize + reopen price rules
- [x] 6.2 Document public meal detail/offering fields and purchase decision workflow for customers
- [x] 6.3 Note breaking change: meal create no longer accepts/requires `total_price`
