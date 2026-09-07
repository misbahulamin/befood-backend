## ADDED Requirements

### Requirement: Order Details list excludes low-balance blocked customers

The system SHALL provide the kitchen Order Details payload from `GET /orders/kitchen/today-order-details/` (and its `/api/v1/web/...` alias) such that each `customers[]` row represents a delivery that will be cooked for. Deliveries MUST continue to exclude meal-off / `skipped` rows. In addition, any delivery whose customer has `CustomerProfile.meal_service_blocked_low_balance=true` MUST be omitted from `customers[]` and MUST NOT increase `count`, even when the delivery status is still meal-on (`scheduled` or other non-skipped cooking statuses). Response structure MUST keep existing fields (`service_date`, `meal_period`, `count`, `customers[]` with `name`, `phone`, `package_name`, `address`, `ingredient_names`, `menu_items_label`). Access MUST remain verified-admin only.

#### Scenario: Blocked meal-on customer not listed

- **WHEN** a verified admin requests today-order-details for a slot that includes an unblocked meal-on delivery and a blocked meal-on delivery
- **THEN** `customers[]` contains only the unblocked customer and `count` equals `1`

#### Scenario: Skipped unblocked still excluded; blocked skipped also absent

- **WHEN** an unblocked customer is `skipped` and a blocked customer is `scheduled` on the same slot
- **THEN** neither appears in `customers[]` (`count` is `0` for those two alone)

#### Scenario: Response keys unchanged when exclusion applies

- **WHEN** blocked customers are omitted from Order Details
- **THEN** the response still uses the same keys and per-row fields as the current Order Details contract without requiring new block-status fields
