## ADDED Requirements

### Requirement: Package per-meal rate is reference average only for delivery charging

The system SHALL continue to compute and expose package-level `per_meal_rate` from finalized cycle plan totals (`total_cost / expected_servings`) as an estimated average meal rate for offering, eligibility estimates, and admin summaries. The system MUST NOT treat `per_meal_rate` as the authoritative amount to debit from a customer wallet when a delivered meal has a published per-slot final meal price.

#### Scenario: Finalized summary still shows average per_meal_rate

- **WHEN** a verified admin finalizes a cycle plan
- **THEN** the summary includes `per_meal_rate` equal to `total_cost / expected_servings` quantized to money precision

#### Scenario: Average rate is not the delivery charge basis when slot price exists

- **WHEN** a package’s `per_meal_rate` is `50.00` and a published lunch slot for a delivery has final meal price `62.00`
- **THEN** delivery charging uses `62.00` and MUST NOT substitute `50.00` from `per_meal_rate`
