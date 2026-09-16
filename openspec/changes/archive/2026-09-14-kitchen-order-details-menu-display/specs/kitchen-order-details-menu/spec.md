## ADDED Requirements

### Requirement: Order details rows include today's published menu ingredients

The system SHALL enrich each customer row on `GET /orders/kitchen/today-order-details/` (and its web-prefixed alias) with the published monthly menu ingredients for that customer’s meal package on the requested `(service_date, meal_period)`. Each row MUST include `ingredient_names` (ordered list of ingredient display name strings) and `menu_items_label` (those names joined with ` + `, e.g. `mach + dhal + vat`). Existing fields `name`, `phone`, `package_name`, and `address` MUST remain. Access MUST remain verified-admin only. Meal-off / skipped deliveries MUST remain excluded.

#### Scenario: Customer row shows slot menu label

- **WHEN** a verified admin requests order details for a slot where a cooking customer’s package has a published menu with ingredients named `mach`, `dhal`, and `vat`
- **THEN** that customer’s row includes `ingredient_names` containing those names and `menu_items_label` equal to `mach + dhal + vat` (same order as `ingredient_names`)

#### Scenario: Existing identity fields preserved

- **WHEN** a verified admin requests order details for a cooking customer
- **THEN** the row still includes `name`, `phone`, `package_name`, and `address` alongside the menu fields

#### Scenario: Package filter still scopes customers

- **WHEN** a verified admin passes `package_public_id` for one package
- **THEN** only cooking customers for that package are returned, each with that package’s slot menu fields for the filtered date/period

### Requirement: Missing published menu does not drop customers

When no published monthly menu slot (or no slot items) exists for a customer’s package on the requested date/period, the system MUST still return the customer row with empty `ingredient_names` and empty or null `menu_items_label`, without fabricating ingredients and without failing the entire response.

#### Scenario: Unpublished slot yields empty menu fields

- **WHEN** a cooking customer’s package has no published ingredients for `(service_date, meal_period)`
- **THEN** the response still lists that customer and sets `ingredient_names` to `[]` with empty or null `menu_items_label`
