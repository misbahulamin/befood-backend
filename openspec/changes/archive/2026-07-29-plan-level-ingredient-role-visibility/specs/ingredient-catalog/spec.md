## MODIFIED Requirements

### Requirement: Admin can manage product catalog for costing

The system SHALL allow verified admins to create, list, update, and delete ingredients (products) used in meal-cycle costing. Each product MUST support either kilogram-based pricing (`price_per_kg` and `customers_per_kg`) or an explicit flat `cost_per_customer`, and MAY include `pieces_per_kg`, `is_active`, `is_customer_visible`, and `notes`. The catalog MUST NOT store a serving `product_role`; role is assigned only on meal-cycle plan lines.

#### Scenario: Create kg-based product

- **WHEN** a verified admin creates a product with `price_per_kg` and `customers_per_kg`
- **THEN** the system stores the product and exposes `cost_per_customer` as `price_per_kg / customers_per_kg`

#### Scenario: Create flat-cost product

- **WHEN** a verified admin creates a product with only `cost_per_customer` (no kg fields)
- **THEN** the system accepts the product and uses that value for line costing

#### Scenario: Reject incomplete pricing

- **WHEN** a verified admin submits a product missing both a complete kg pair and `cost_per_customer`
- **THEN** the system returns a validation error and does not create the product

#### Scenario: Create without product_role

- **WHEN** a verified admin creates an ingredient without sending `product_role`
- **THEN** the system accepts the ingredient and does not persist a catalog-level role

#### Scenario: Reject or ignore product_role on ingredient write

- **WHEN** a verified admin includes `product_role` on ingredient create or update
- **THEN** the system does not store a catalog role (field rejected as unknown or ignored per API contract) and role remains unset until assigned on a plan line

#### Scenario: Non-admin denied

- **WHEN** a customer or unauthenticated client calls ingredient write endpoints
- **THEN** the system denies access (`401` or `403` as applicable)

## REMOVED Requirements

### Requirement: Product role supports cycle fill validation

**Reason**: Global ingredient role cannot express per–meal-package differences; finalize and schedule now use plan-line `product_role`.

**Migration**: Admins set `product_role` on each `MealCyclePlanLine` when building or replacing the servings matrix. Existing lines are backfilled from the former ingredient role during migration.
