## Purpose

Customer-safe public meal pricing and finalized cycle offering details for purchase decisions.

## Requirements

### Requirement: Public meal list exposes pricing status

The system SHALL allow unauthenticated clients to list active meals with `total_price` (nullable), derived `per_meal_price` (nullable when unpriced), and `pricing_status` of `priced` or `unpriced`.

#### Scenario: Priced meal on list

- **WHEN** a public client lists meals and a meal has a non-null `total_price`
- **THEN** that meal appears with `pricing_status` `priced` and a non-null `total_price`

#### Scenario: Unpriced meal on list

- **WHEN** a meal has never been published from a finalized cycle (`total_price` is null)
- **THEN** the list item shows `pricing_status` `unpriced` and `total_price` is null

### Requirement: Public meal detail shows finalized cycle offering

The system SHALL provide a public meal detail response that includes customer-safe finalized cycle offering data for purchase decisions: cycle year/month, `cycle_days`, `total_meals`, package total, per-meal rate, high-level cost bands from snapshots (`product_cost`, `other_cost`, `profit`), `finalized_at`, and menu items (`name`, `product_role`, `servings_count`).

#### Scenario: Detail with current offering

- **WHEN** a public client retrieves a meal that has at least one finalized cycle plan
- **THEN** the response includes `current_cycle_offering` built from the latest finalized plan (by year, month, then finalized_at) with menu servings and published totals

#### Scenario: Detail without finalized plan

- **WHEN** a public client retrieves a meal with no finalized cycle plan
- **THEN** `current_cycle_offering` is null and the response still includes basic meal fields

### Requirement: Public responses hide admin-sensitive costing inputs

Public meal responses MUST NOT include ingredient purchase fields such as `price_per_kg`, draft cycle plans, or admin-only notes.

#### Scenario: No supplier unit prices on public detail

- **WHEN** a public client retrieves meal detail with a current offering
- **THEN** offering menu items do not include `price_per_kg` or `customers_per_kg`

### Requirement: Meal create does not require total price

Verified admins MUST be able to create a meal package without providing `total_price`. Created meals SHALL start as `unpriced` until a linked cycle plan is finalized.

#### Scenario: Create meal without total_price

- **WHEN** a verified admin creates a meal with name, thumbnail, and meal_type only (no total_price)
- **THEN** the meal is created with `total_price` null and `pricing_status` `unpriced`

#### Scenario: Manual total_price write rejected or ignored on meal APIs

- **WHEN** a verified admin attempts to set `total_price` through meal create/update APIs
- **THEN** the system does not treat that value as the published source of truth (field is not writable for publishing)

### Requirement: Orders require published meal price

The system MUST reject creating a customer order for a meal whose `total_price` is null.

#### Scenario: Order blocked for unpriced meal

- **WHEN** a customer attempts to order a meal with null `total_price`
- **THEN** the system returns a validation error and does not create the order
