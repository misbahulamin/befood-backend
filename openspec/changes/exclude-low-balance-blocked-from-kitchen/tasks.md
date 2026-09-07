## 1. Shared demand exclusion

- [x] 1.1 In `orders/services/meal_demand.py` `_demand_queryset`, exclude deliveries where `subscription__customer__meal_service_blocked_low_balance=True` OR `order__customer__meal_service_blocked_low_balance=True` (mirror `auto_meal_delivery.eligible_delivery_queryset`)
- [x] 1.2 Confirm `get_demand`, `build_kitchen_requirement`, `build_kitchen_order_details`, and snapshot writers all inherit the exclude with no divergent per-endpoint filters
- [x] 1.3 Add a short English comment on `_demand_queryset` documenting alignment with auto meal delivery skip-on-block

## 2. Tests

- [x] 2.1 Add/extend `orders/tests/test_meal_demand.py` cases: blocked meal-on customer omitted from `get_demand` / kitchen requirement counts and ingredient scaling
- [x] 2.2 Assert blocked meal-on customer omitted from `build_kitchen_order_details` `customers[]` and `count`
- [x] 2.3 Assert blocked+skipped delivery contributes to neither expected nor meal-off
- [x] 2.4 Assert unblocked customers still counted/listed; response keys unchanged for both kitchen endpoints
- [x] 2.5 Run targeted meal-demand / kitchen tests and fix regressions

## 3. Documentation

- [x] 3.1 Update `orders/docs/backend/meal-demand-kitchen-planning.md` mental model: low-balance meal-stop blocked customers excluded from live demand/kitchen (not counted as meal-off)
- [x] 3.2 Update `orders/docs/frontend/meal-demand-kitchen-planning.md` so Admin SPA notes that blocked customers never appear in today-meal-requirement or today-order-details
