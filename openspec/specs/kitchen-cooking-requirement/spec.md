## Purpose

Lean kitchen/admin API for today's cooking headcount and ingredient quantities scaled by final cooking count for a service date and meal period.
## Requirements
### Requirement: Kitchen today cooking requirement API

The system SHALL provide a lean Kitchen/Admin endpoint that returns the cooking requirement for a single `(service_date, meal_period)` without admin analytics nesting. By default, when `service_date` and `meal_period` are omitted, the system MUST use today’s date in the meal-off settings timezone and infer meal period from the business clock in that timezone: if local time is strictly before the configured `dinner_off_time`, default `meal_period` is `lunch`; otherwise default `meal_period` is `dinner`. Callers MAY override with explicit `service_date` and `meal_period` query params. Response MUST include: service date, meal period, final cooking count (people to cook for), expected count, meal-off count, `confirmation_status`, and ingredient quantity list. Access MUST be limited to verified admins (same gate as the existing kitchen board); customers MUST be denied.

#### Scenario: Morning default is today lunch

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 10:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=lunch` and includes final cooking count and ingredients

#### Scenario: Afternoon default is today dinner

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 15:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=dinner`

#### Scenario: Explicit override

- **WHEN** a verified admin requests `service_date=2026-08-10` and `meal_period=dinner`
- **THEN** the response is scoped to that date and dinner regardless of current clock

#### Scenario: Customer denied kitchen requirement

- **WHEN** a verified customer calls the kitchen today-requirement endpoint
- **THEN** the system denies access with `401` or `403`

### Requirement: Ingredient quantities scale with final cooking count

The system SHALL calculate kitchen ingredient requirements for a `(service_date, meal_period)` by resolving the published monthly menu schedule ingredients assigned to that slot for each package that has demand, then aggregating quantities across packages. For each ingredient with a complete kilogram pricing pair (`price_per_kg` and `customers_per_kg`), per-person kilograms MUST be `1 / customers_per_kg`, and total kilograms MUST be `per_person_kg × package_final_cooking_count`, summed across packages that include that ingredient on the slot. Quantities MUST use decimal arithmetic (not binary floats) and MUST be returned with unit `kg` when derived from kg yield. Ingredients present on the slot without resolvable kg yield MUST still appear in the list with quantity `null` (or omitted quantity) and a flag indicating quantity could not be computed, without failing the entire requirement response. Flat `cost_per_customer`-only ingredients MUST NOT invent a kilogram quantity.

#### Scenario: Rice scaled by final count

- **WHEN** dinner final cooking count is `450` for a package whose published dinner slot includes Rice with `customers_per_kg=10/3` (0.3 kg per person) and no other package contributes Rice
- **THEN** the ingredient list includes Rice with total quantity `135` kg (within documented decimal precision)

#### Scenario: Multi-package aggregation

- **WHEN** Premium final dinner count is `170` and Regular is `250`, and both slots include Chicken with the same `customers_per_kg`
- **THEN** Chicken total quantity equals per-person kg × `(170 + 250)`

#### Scenario: Flat-cost spice without kg yield

- **WHEN** a slot ingredient has only flat `cost_per_customer` and no `customers_per_kg`
- **THEN** the kitchen response still lists the ingredient for awareness but does not invent a kg quantity

### Requirement: Missing menu does not invent ingredients

When no published monthly menu schedule assignment exists for a package’s `(service_date, meal_period)`, the system MUST still return cooking headcount for that package/period and MUST return an empty or partial ingredient list for packages lacking menu data, without fabricating ingredients from the cycle plan’s full month matrix alone unless the design explicitly maps slot assignments only. The response MUST indicate when ingredient data is incomplete for the slot.

#### Scenario: Counts without published slot menu

- **WHEN** demand exists for `(D, lunch)` but the package’s monthly menu schedule has no published ingredients for that slot
- **THEN** final cooking count is still returned and the ingredient list is empty or marked incomplete for that package

### Requirement: Late low-balance resume must not inflate past-cutoff cooking counts

After a customer’s low-balance meal-stop block is cleared because wallet balance recovered, the kitchen today-requirement for a `(service_date, meal_period)` whose meal-off cutoff has already passed MUST NOT increase `final_cooking_count` solely due to that resume. Ingredient quantities that scale from `final_cooking_count` MUST remain consistent with that stable cooking headcount. A late-resumed customer MAY move from `low_balance_blocked_count` into meal-off/skipped accounting for that slot, but MUST NOT appear in final cooking for an already-cutoff-passed period.

#### Scenario: Morning kitchen count stays flat after late lunch resume

- **WHEN** lunch cutoff has passed, kitchen lunch `final_cooking_count` is `30`, and a previously low-balance-blocked customer recharges and resumes
- **THEN** lunch `final_cooking_count` remains `30` and ingredient kg derived from final cooking do not increase for that customer

#### Scenario: Dinner requirement can include customer before dinner cutoff

- **WHEN** the same customer resumes after lunch cutoff but before dinner cutoff with dinner meal ON (`scheduled`)
- **THEN** dinner kitchen requirement MAY include the customer in `final_cooking_count` while lunch remains excluded

### Requirement: Post-charge meal-stop exclusion appears in kitchen cooking counts without waiting for evening cron

The system SHALL continue to exclude customers with `CustomerProfile.meal_service_blocked_low_balance=true` from Kitchen Today cooking headcount and ingredient scaling (`final_cooking_count` and related demand buckets that already omit low-balance blocked customers). When a successful meal-payment debit causes immediate meal-stop blocking under `post-meal-charge-meal-stop`, a subsequent kitchen today-meal-requirement (or today-order-details) request for an affected dinner/lunch slot MUST omit that customer from cook counts without requiring the 20:00 Asia/Dhaka wallet-threshold cron to have run. Kitchen MUST NOT depend on a separate cache invalidation step; live querysets over the block flag are sufficient. This change MUST NOT require kitchen to recompute exclusion from live `Wallet.balance < meal_stop_threshold` in place of the block flag.

#### Scenario: After lunch charge block, dinner kitchen count drops before 20:00

- **WHEN** lunch auto-delivery successfully charges a customer so post-debit balance is below `meal_stop_threshold`, meal-stop block is applied immediately, and a verified admin then requests kitchen today-meal-requirement for today’s dinner before 20:00 Asia/Dhaka
- **THEN** that customer is not included in `final_cooking_count` for dinner

#### Scenario: Kitchen still uses block flag not raw balance for cook exclusion

- **WHEN** a customer has spendable balance below `meal_stop_threshold` but `meal_service_blocked_low_balance` is still `false`
- **THEN** kitchen cooking exclusion for that customer remains governed by the block flag (and other existing live-delivery/skip rules), not by a new live-balance cook formula introduced in this change

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

