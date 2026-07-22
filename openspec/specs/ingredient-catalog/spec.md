## Purpose

Product catalog for meal-cycle costing: ingredients with kilogram-based or flat per-customer pricing, plus product roles used in cycle fill validation.

## Requirements

### Requirement: Admin can manage product catalog for costing

The system SHALL allow verified admins to create, list, update, and delete ingredients (products) used in meal-cycle costing. Each product MUST support either kilogram-based pricing (`price_per_kg` and `customers_per_kg`) or an explicit flat `cost_per_customer`, and MAY include `pieces_per_kg`, `product_role`, `is_active`, and `notes`.

#### Scenario: Create kg-based product

- **WHEN** a verified admin creates a product with `price_per_kg` and `customers_per_kg`
- **THEN** the system stores the product and exposes `cost_per_customer` as `price_per_kg / customers_per_kg`

#### Scenario: Create flat-cost product

- **WHEN** a verified admin creates a product with only `cost_per_customer` (no kg fields)
- **THEN** the system accepts the product and uses that value for line costing

#### Scenario: Reject incomplete pricing

- **WHEN** a verified admin submits a product missing both a complete kg pair and `cost_per_customer`
- **THEN** the system returns a validation error and does not create the product

#### Scenario: Non-admin denied

- **WHEN** a customer or unauthenticated client calls ingredient write endpoints
- **THEN** the system denies access (`401` or `403` as applicable)

### Requirement: Product role supports cycle fill validation

The system SHALL allow each product to declare a `product_role` of `main`, `side`, `staple`, `seasoning`, or `other` so cycle finalize rules can treat main proteins distinctly from staples.

#### Scenario: Assign main role

- **WHEN** a verified admin sets `product_role` to `main` on Chicken
- **THEN** that product’s servings count toward the main-fill total on finalize
