## ADDED Requirements

### Requirement: Kitchen order summary includes package-wise meal rows

The system SHALL expose package-wise meal summary data for a kitchen cooking slot `(service_date, meal_period)` such that each package row includes package public id, package name, total customers contributing deliveries for that slot, expected meal count, meal-off count, and final cooking count. Overall slot totals MUST equal the sum of the package-wise expected, meal-off, and final cooking counts for the same filtered result. Package identity MUST use the delivery’s resolved meal package (`MealCategory`), consistent with existing meal demand forecasting.

#### Scenario: Student and Regular package summary

- **WHEN** a verified admin requests the kitchen cooking summary for date `D` and `lunch` where Student has 10 final cooking meals and Regular has 8 final cooking meals (no meal-offs)
- **THEN** the response includes a Student package row with `final_cooking_count=10` and a Regular package row with `final_cooking_count=8`, and overall `final_cooking_count=18`

#### Scenario: Meal-off reduces package final count

- **WHEN** Student has 12 expected lunch deliveries on date `D` and 2 are skipped
- **THEN** the Student package row shows `expected_meal_count=12`, `meal_off_count=2`, and `final_cooking_count=10`

### Requirement: Item-wise cooking calculation consolidates across packages

The system SHALL compute item-wise cooking calculation from published monthly menu slot ingredients for each package with `final_cooking_count > 0`, aggregating the same ingredient across packages. For each aggregated ingredient, the response MUST include:

- Ingredient public id and name
- `customer_count` equal to the sum of `final_cooking_count` from packages whose published slot includes that ingredient
- `package_contributions` listing each contributing package’s public id, name, and that package’s `final_cooking_count` for the slot
- Existing kilogram quantity fields when kg yield is available (`quantity`, `unit`, `kg_per_person`, `quantity_available`), without inventing kg for flat-cost-only ingredients

Items present in only one package MUST still appear with a single contribution and `customer_count` equal to that package’s final cooking count.

#### Scenario: Shared item sums headcount across packages

- **WHEN** Student final count is `10` with slot items Dal, Vegetable, Rice and Regular final count is `3` with slot items Dal, Fish, Rice
- **THEN** Dal and Rice each have `customer_count=13` with contributions from Student (`10`) and Regular (`3`), Vegetable has `customer_count=10` from Student only, and Fish has `customer_count=3` from Regular only

#### Scenario: Kilogram quantity still scales by final counts

- **WHEN** Dal has resolvable `customers_per_kg` and is included for Student (`10`) and Regular (`3`)
- **THEN** Dal’s kilogram `quantity` equals per-person kg × `13` (within documented decimal precision) and `customer_count` is `13`

#### Scenario: Flat-cost item without kg yield still lists headcount

- **WHEN** an ingredient on the slot has no resolvable kg yield
- **THEN** the item still appears with `customer_count` and `package_contributions`, `quantity_available=false`, and no invented kilogram quantity

### Requirement: Kitchen summary filters align with meal demand

The kitchen cooking summary MUST accept optional query filters `service_date`, `meal_period` (`lunch`|`dinner`), and `package_public_id`. When `service_date` and `meal_period` are omitted, defaults MUST match the existing kitchen today default slot resolution. When `package_public_id` is provided, package rows and item aggregations MUST include only that package’s demand and menu items. Invalid `meal_period` or unparsable `service_date` MUST return `400`. Access MUST remain limited to verified admins.

#### Scenario: Filter by package scopes packages and items

- **WHEN** a verified admin requests the kitchen summary for date `D`, `dinner`, and Student’s `package_public_id`
- **THEN** `packages` contains only Student and item `customer_count` values reflect only Student’s final cooking count

#### Scenario: Default slot without filters

- **WHEN** a verified admin calls the kitchen summary endpoint with no query params before the configured dinner off time in the meal-off timezone
- **THEN** the response uses today’s date and `meal_period=lunch`

#### Scenario: Customer denied

- **WHEN** a verified customer calls the kitchen cooking summary endpoint
- **THEN** the system denies access with `401` or `403`

### Requirement: Printable sheet data is the filtered summary payload

The system SHALL treat the filtered kitchen cooking summary response as the sole data contract for a printable kitchen sheet. The printable representation MUST be able to render: (1) package-wise summary, (2) item-wise cooking calculation including `customer_count` and contributions, and (3) necessary prep notes including at least `confirmation_status` and an incomplete-menu warning when `ingredients_incomplete` is true. The API MUST NOT require a separate print-only endpoint for v1.

#### Scenario: Same filters for screen and print

- **WHEN** an admin applies `service_date`, `meal_period`, and optional `package_public_id` and then generates a printable sheet
- **THEN** the sheet content is derived from the same summary response returned for those filters
