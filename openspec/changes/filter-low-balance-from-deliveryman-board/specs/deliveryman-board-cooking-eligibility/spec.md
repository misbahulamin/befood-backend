## ADDED Requirements

### Requirement: Deliveryman today-board omits low-balance meal-stop blocked customers
The system SHALL ensure `GET /user_management/deliveryman/deliveries/today-board/` returns only zone-scoped deliveries for customers who are cooking-eligible for the active meal period. Customers with `CustomerProfile.meal_service_blocked_low_balance=true` MUST be omitted from the board customer lists, location `delivery_count` values, period `total_count`, and top-level `total_count`, even when their lunch/dinner preference remains on and an `OrderDelivery` row remains `scheduled`. Exclusion MUST use the meal-stop **block flag** (same rule as kitchen `today-meal-requirement` / `today-order-details`), NOT a live wallet-balance comparison against `meal_stop_threshold`. Response field names and nesting MUST remain unchanged. Deliveryman payloads MUST continue to omit customer wallet balances.

#### Scenario: Blocked meal-on customer hidden; unblocked peer shown
- **WHEN** a Delivery Man’s assigned zone has two active-location customers with `scheduled` deliveries for the active meal period, and only one customer has `meal_service_blocked_low_balance=true`
- **THEN** the today-board includes only the unblocked customer and `total_count` equals `1`

#### Scenario: All zone customers blocked yields empty board for active period
- **WHEN** every scheduled delivery in the rider’s zone for the active meal period belongs to a low-balance meal-stop blocked customer
- **THEN** the today-board returns `total_count` `0` and empty location groups for that period (zone metadata and active period may still be present)

#### Scenario: Unblocked meal-on customer still listed
- **WHEN** a zone customer has a scheduled delivery for the active meal period and `meal_service_blocked_low_balance=false`
- **THEN** that customer appears on the today-board as before (name, address snapshots, location priority ordering unchanged)

#### Scenario: Parity with kitchen cooking eligibility rule
- **WHEN** kitchen today-order-details / today-meal-requirement omit a customer solely because `meal_service_blocked_low_balance=true`
- **THEN** the deliveryman today-board for the same service date and meal period MUST also omit that customer

### Requirement: Deliveryman docs state cooking-eligibility filter
The system SHALL document in deliveryman zone-delivery frontend (and backend) docs that the today-board excludes low-balance meal-stop blocked customers and therefore may list fewer customers than “all meal-on in zone.”

#### Scenario: Frontend doc mentions meal-stop exclusion
- **WHEN** an engineer reads `delivery_zones/docs/frontend/zone-based-delivery.md` (or the deliveryman board section referenced from deliveryman auth docs)
- **THEN** the doc states that customers with meal service blocked for low balance are omitted from the today-board even if lunch/dinner remains on
