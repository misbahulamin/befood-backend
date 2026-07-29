## MODIFIED Requirements

### Requirement: Admin can manage product catalog for costing

The system SHALL allow verified admins to create, list, update, and delete ingredients (products) used in meal-cycle costing. Each product MAY omit pricing entirely, MAY use kilogram-based pricing (`price_per_kg` and `customers_per_kg`), MAY use an explicit flat `cost_per_customer` (per-serving cooking cost for one customer or one piece), or MAY use **both** kg pricing and flat `cost_per_customer` together. Each product MAY include `pieces_per_kg`, `is_active`, `is_customer_visible`, and `notes`. The catalog MUST NOT store a serving `product_role`; role is assigned only on meal-cycle plan lines. Flat `cost_per_customer` is optional on create and update; when omitted or null and kg pricing is absent, the product remains valid in the catalog with no resolvable cost until pricing is supplied.

Read-only `resolved_cost_per_customer` MUST be the kilogram-derived unit cost (`price_per_kg / customers_per_kg`) when a complete kg pair is present, and MUST be `null` when kg pricing is absent. It MUST NOT fall back to flat `cost_per_customer`. When both kg and flat are present, meal-cycle line costing MUST add them (see meal-cycle-costing); the catalog MUST allow both fields to be stored concurrently.

#### Scenario: Create kg-based product

- **WHEN** a verified admin creates a product with `price_per_kg` and `customers_per_kg` and no flat cost
- **THEN** the system stores the product and returns `resolved_cost_per_customer` as `price_per_kg / customers_per_kg`

#### Scenario: Create flat-cost product

- **WHEN** a verified admin creates a product with only `cost_per_customer` (no kg fields)
- **THEN** the system accepts the product, returns `resolved_cost_per_customer` as null, and stores the flat value for additive line costing

#### Scenario: Create product with both kg and flat cost

- **WHEN** a verified admin creates a product with a complete kg pair and a positive `cost_per_customer`
- **THEN** the system stores both, returns kg-derived `resolved_cost_per_customer`, and retains the flat `cost_per_customer` for additive costing

#### Scenario: Create product without pricing

- **WHEN** a verified admin creates a product with neither a complete kg pair nor `cost_per_customer`
- **THEN** the system stores the product and returns `resolved_cost_per_customer` as null

#### Scenario: Create with optional per-serving cost

- **WHEN** a verified admin creates a product and sets optional `cost_per_customer` to a positive amount
- **THEN** the system stores that flat per-serving cooking cost for one customer or one piece

#### Scenario: Omit optional per-serving cost

- **WHEN** a verified admin creates or updates a product and leaves `cost_per_customer` empty while also omitting kg pricing
- **THEN** the system accepts the request and does not invent a zero cost

#### Scenario: Reject incomplete kg pair

- **WHEN** a verified admin submits only one of `price_per_kg` or `customers_per_kg`
- **THEN** the system returns a validation error and does not create or update the product

#### Scenario: Create without product_role

- **WHEN** a verified admin creates an ingredient without sending `product_role`
- **THEN** the system accepts the ingredient and does not persist a catalog-level role

#### Scenario: Reject or ignore product_role on ingredient write

- **WHEN** a verified admin includes `product_role` on ingredient create or update
- **THEN** the system does not store a catalog role (field rejected as unknown or ignored per API contract) and role remains unset until assigned on a plan line

#### Scenario: Non-admin denied

- **WHEN** a customer or unauthenticated client calls ingredient write endpoints
- **THEN** the system denies access (`401` or `403` as applicable)
