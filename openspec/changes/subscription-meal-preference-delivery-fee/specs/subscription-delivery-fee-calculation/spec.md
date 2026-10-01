## ADDED Requirements

### Requirement: Canonical subscription delivery fee calculation

The system SHALL provide a single backend function that computes monthly delivery fee from meal preference and quantity. Web and mobile clients MUST NOT hardcode fee amounts; they MUST display values returned by quote or subscription APIs.

#### Scenario: Lunch-only fee

- **WHEN** preference is `lunch` for any valid quantity
- **THEN** monthly delivery fee is `200.00` BDT with rule code indicating single-period

#### Scenario: Dinner-only fee

- **WHEN** preference is `dinner` for any valid quantity
- **THEN** monthly delivery fee is `200.00` BDT with rule code indicating single-period

#### Scenario: Both fee tier 1–3

- **WHEN** preference is `both` and quantity is between 1 and 3 inclusive
- **THEN** monthly delivery fee is `400.00` BDT

#### Scenario: Both fee tier 4–5

- **WHEN** preference is `both` and quantity is 4 or 5
- **THEN** monthly delivery fee is `350.00` BDT

#### Scenario: Both fee tier 6+

- **WHEN** preference is `both` and quantity is 6 or greater
- **THEN** monthly delivery fee is `300.00` BDT

#### Scenario: Boundary quantity 3 is top of first both tier

- **WHEN** preference is `both` and quantity is `3`
- **THEN** fee is `400.00` (not the middle tier)

#### Scenario: Boundary quantity 4 is middle tier

- **WHEN** preference is `both` and quantity is `4`
- **THEN** fee is `350.00`

### Requirement: Subscription quote preview

The system SHALL expose `POST /api/v1/subscriptions/quote/` that accepts `plan_public_id`, optional `meal_preference`, and optional `quantity`, validates preference against the package, and returns normalized `meal_preference`, `quantity`, `monthly_delivery_fee`, and `fee_rule_code` without creating a subscription.

#### Scenario: Quote both for two persons

- **WHEN** a verified customer posts quote with a both package, `meal_preference=both`, `quantity=2`
- **THEN** the response includes `monthly_delivery_fee` of `400.00` and does not create a subscription row

#### Scenario: Quote does not debit wallet

- **WHEN** quote succeeds
- **THEN** no wallet ledger or delivery-fee payment row is created

### Requirement: Delivery fee debit path unchanged

Subscribe and quote MUST NOT automatically call `charge_delivery_fee`. Monthly delivery-fee wallet debit remains the existing admin manual flow (or future explicit product change). Fee calculation is informational/suggested amount only in this capability.

#### Scenario: Subscribe does not create delivery_fee_payment

- **WHEN** a customer successfully subscribes with any preference
- **THEN** no `delivery_fee_payment` wallet transaction is created by subscribe
