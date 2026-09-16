## ADDED Requirements

### Requirement: Kitchen requirement omits low-balance blocked customers

The system SHALL ensure `GET /orders/kitchen/today-meal-requirement/` (and its `/api/v1/web/...` alias) omits customers with `meal_service_blocked_low_balance=true` from cooking headcount and ingredient scaling. Omitted customers MUST NOT appear in overall or package `expected_meal_count`, `meal_off_count`, `final_cooking_count`, or `total_customers`, and MUST NOT increase ingredient `quantity` / contribution `customer_count`. Response field names and nesting MUST remain unchanged from the existing kitchen requirement contract. Access and default slot resolution rules MUST remain verified-admin-only and otherwise unchanged.

#### Scenario: Blocked customer reduces final cooking and ingredients

- **WHEN** a verified admin requests today-meal-requirement for a slot where 10 unblocked meal-on deliveries and 2 blocked meal-on deliveries exist for the same package with published kg ingredients
- **THEN** `final_cooking_count` is `10` (not `12`) and ingredient kilograms scale using `10`

#### Scenario: Response shape unchanged

- **WHEN** a verified admin calls today-meal-requirement with blocked customers present in the slot
- **THEN** the JSON still exposes the same top-level and package/ingredient keys as before (no required new fields for the block)

#### Scenario: Web alias matches shared path

- **WHEN** a verified admin calls the web-prefixed kitchen today-meal-requirement alias for the same filters
- **THEN** counts match the non-prefixed endpoint after low-balance exclusion
