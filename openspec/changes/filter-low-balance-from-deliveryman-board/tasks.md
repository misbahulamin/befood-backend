## 1. Board queryset eligibility

- [x] 1.1 Exclude `meal_service_blocked_low_balance` customers from `zone_scoped_deliveries` / `build_deliveryman_board` using the same subscription/order customer Q as kitchen (`meal_demand._low_balance_blocked_q` or a shared public helper)
- [x] 1.2 Ensure `total_count`, location `delivery_count`, and customer lists all reflect the filtered queryset (no post-count drift)

## 2. Tests

- [x] 2.1 Add deliveryman today-board test: one blocked + one unblocked zone peer → only unblocked customer returned and `total_count == 1`
- [x] 2.2 Add/extend case where all zone scheduled deliveries are blocked → empty board (`total_count == 0`) for the active period
- [x] 2.3 Run `delivery_zones.tests.test_zone_based_delivery` (or targeted board tests) and confirm existing board tests still pass

## 3. Docs

- [x] 3.1 Update `delivery_zones/docs/frontend/zone-based-delivery.md` today-board section: omit low-balance meal-stop blocked customers even when lunch/dinner remains on
- [x] 3.2 Update `delivery_zones/docs/backend/zone-based-delivery.md` with the same eligibility rule and kitchen parity note
