## Why

Kitchen cook counts and Order Details lists still include customers whose `CustomerProfile.meal_service_blocked_low_balance` is `true`. Auto meal delivery already skips those customers, so the kitchen can over-cook and print names for people who will not be served until wallet balance recovers.

## What Changes

- Exclude low-balance meal-stop–blocked customers from the shared meal-demand queryset used by kitchen (and aligned admin demand) calculations.
- `GET /orders/kitchen/today-meal-requirement/` (and web alias): blocked customers MUST NOT contribute to `expected_meal_count`, `meal_off_count`, `final_cooking_count`, `total_customers`, package rows, or ingredient scaling.
- `GET /orders/kitchen/today-order-details/` (and web alias): blocked customers MUST NOT appear in `customers[]` or `count`, even if their delivery is still meal-on (`scheduled` / not skipped).
- Response JSON field names and nesting stay the same (no new fields required for this fix).
- Reuse the same customer-path exclude already used by auto meal delivery (`subscription__customer` OR `order__customer`).

## Capabilities

### New Capabilities

- `kitchen-order-details-eligibility`: Per-customer kitchen Order Details list eligibility — exclude low-balance meal-stop–blocked customers while keeping the existing response shape and meal-off exclusions.

### Modified Capabilities

- `meal-demand-forecasting`: Shared demand calculation MUST exclude deliveries whose customer has `meal_service_blocked_low_balance=true` from expected / meal-off / final / customer counts.
- `kitchen-cooking-requirement`: Kitchen today-requirement aggregates and ingredient kg MUST reflect that exclusion; response contract otherwise unchanged.

## Impact

- Code: `orders/services/meal_demand.py` (`_demand_queryset`, thus `get_demand`, `build_kitchen_requirement`, `build_kitchen_order_details`, snapshot writers); kitchen views remain thin.
- APIs: `/orders/kitchen/today-meal-requirement/`, `/orders/kitchen/today-order-details/`, and web-prefixed aliases; live `/orders/meal-statistics/` and new demand snapshots also align via the shared service.
- Tests: `orders/tests/test_meal_demand.py` (and related kitchen demand cases).
- Docs: `orders/docs/backend/meal-demand-kitchen-planning.md` and frontend kitchen planning notes.
- No migration; flag already exists on `CustomerProfile`. Not **BREAKING** for clients that ignore unknown fields — counts may drop for blocked customers (intended behavior fix).
