## Why

Deliverymen currently see every zone customer with lunch/dinner still “on” (`scheduled` delivery), including customers whose meal service is paused by low-balance meal-stop (`meal_service_blocked_low_balance=true`). Kitchen already excludes those customers from cooking (`today-meal-requirement` / `today-order-details`), so riders are asked to deliver meals that were never cooked. Align the deliveryman today-board with kitchen cooking eligibility so only customers who will actually receive a meal appear.

## What Changes

- Exclude low-balance meal-stop blocked customers from the deliveryman today-board queryset (same rule kitchen and auto-delivery already use: `CustomerProfile.meal_service_blocked_low_balance=true`).
- Keep meal-on preference / `scheduled` status unchanged for those customers — only hide them from rider ops surfaces that imply a physical delivery.
- Update deliveryman board tests and zone-based delivery frontend/backend docs to document the exclusion.
- **Non-breaking** for API shape: same response fields; counts and customer lists simply omit blocked customers.

## Capabilities

### New Capabilities

- `deliveryman-board-cooking-eligibility`: Deliveryman today-board includes only customers eligible for kitchen cooking / physical delivery for the active meal period (excludes low-balance meal-stop blocked customers while lunch/dinner toggle may still be on).

### Modified Capabilities

- (none in `openspec/specs/` — deliveryman board behavior was introduced under change `zone-based-delivery-management` and is not yet synced to main specs; this change adds the eligibility delta as a new capability spec.)

## Impact

- **Code:** `delivery_zones/services/board.py` (`zone_scoped_deliveries` / `build_deliveryman_board`); reuse or mirror the existing low-balance exclude Q from `orders.services.meal_demand` / auto-delivery.
- **API:** `GET /user_management/deliveryman/deliveries/today-board/` — smaller `total_count` / location groups when blocked customers exist in the zone.
- **Mark delivery:** unchanged zone scoping; blocked customers should not appear on the board (mark remains zone-scoped for any existing delivery id).
- **Docs:** `delivery_zones/docs/frontend/zone-based-delivery.md`, `delivery_zones/docs/backend/zone-based-delivery.md`.
- **Tests:** `delivery_zones/tests/test_zone_based_delivery.py`.
- **Out of scope:** changing kitchen APIs, wallet threshold cron, meal preference toggles, or exposing wallet balances on deliveryman payloads.
