## Purpose

Monthly operational cost ledger for verified admins: cost items, target meal quantity, and per-meal operational cost resolution by year and month for meal cycle costing.

## Requirements

### Requirement: Monthly operational cost ledger

The system SHALL allow a verified admin to manage one operational cost month per calendar `(year, month)`, uniquely constrained. Each month MUST support zero or more cost items with a human-readable `name` and a monetary `amount` (decimal, no binary floating point). The system MUST compute `total_operational_cost` as the sum of item amounts quantized to the project money precision (`0.01`).

#### Scenario: Create July operational cost month with items

- **WHEN** a verified admin creates an operational cost month for year `2026` month `7` with items Office Rent `50000.00`, Electricity `10000.00`, Employee Salary `200000.00`, and Chef Salary `50000.00`
- **THEN** the system stores the month and items and `total_operational_cost` equals `310000.00`

#### Scenario: Unique year-month

- **WHEN** a verified admin attempts to create a second operational cost month for the same year and month
- **THEN** the system rejects the request with a conflict or validation error

#### Scenario: Add edit delete items

- **WHEN** a verified admin adds, updates, or deletes items on a draft-capable operational cost month
- **THEN** the system persists the change and recalculates `total_operational_cost`

### Requirement: Target meal quantity and per-meal operational cost

The system SHALL store a positive integer `target_meal_quantity` on each operational cost month. When `target_meal_quantity` is greater than zero, the system MUST compute:

```text
per_meal_operational_cost = total_operational_cost ÷ target_meal_quantity
```

using decimal arithmetic and quantizing the result to money precision (`0.01`). The system MUST reject setting `target_meal_quantity` to zero or a negative value.

#### Scenario: July per-meal operational cost

- **WHEN** an operational cost month has `total_operational_cost` `310000.00` and `target_meal_quantity` `10000`
- **THEN** `per_meal_operational_cost` equals `31.00`

#### Scenario: Reject zero target meals

- **WHEN** a verified admin attempts to set `target_meal_quantity` to `0`
- **THEN** the system returns a validation error

#### Scenario: Empty ledger with target set

- **WHEN** an operational cost month has no items and `target_meal_quantity` `10000`
- **THEN** `total_operational_cost` is `0.00` and `per_meal_operational_cost` is `0.00`

### Requirement: Verified admin APIs for operational cost

The system SHALL expose authenticated APIs for creating, retrieving, updating, and deleting operational cost months and their items. All such endpoints MUST require `IsVerifiedAdmin` (authenticated, active, verified admin profile or superuser, ADMIN group). Unauthenticated, customer, or non-verified admin callers MUST receive `401` or `403` as appropriate and MUST NOT receive ledger or per-meal operational cost payloads.

#### Scenario: Verified admin lists months

- **WHEN** a verified admin lists operational cost months
- **THEN** the response includes months with totals, target meal quantity, and per-meal operational cost

#### Scenario: Customer denied

- **WHEN** an authenticated customer requests operational cost months or items
- **THEN** the system denies access and does not return cost ledger data

#### Scenario: Unauthenticated denied

- **WHEN** an unauthenticated client requests operational cost endpoints
- **THEN** the system returns `401 Unauthorized`

### Requirement: Resolve per-meal operational cost by year and month

The system SHALL provide a service-layer resolver that, given `year` and `month`, returns the operational cost month’s `per_meal_operational_cost` when a month exists with `target_meal_quantity > 0`. When no such month exists, the resolver MUST signal a domain validation failure (not silently return zero).

#### Scenario: Resolver finds July rate

- **WHEN** July `2026` has target meals and a computed per-meal rate `31.00`
- **THEN** resolving year `2026` month `7` returns `31.00`

#### Scenario: Resolver fails when month missing

- **WHEN** no operational cost month exists for year `2026` month `8`
- **THEN** resolving that month fails with a validation error identifying the missing month
