## ADDED Requirements

### Requirement: Costing fails when ingredient cost is unresolved

The system SHALL NOT treat a missing ingredient cost as zero. When building a plan summary or finalizing a plan, if any line’s ingredient has no resolvable per-serving cost (neither complete kg pricing nor flat `cost_per_customer`), the system MUST return a validation error identifying the ingredient.

#### Scenario: Summary rejected for unpriced line ingredient

- **WHEN** a verified admin requests summary for a plan that includes an ingredient with no resolvable cost
- **THEN** the system returns a validation error and does not return fabricated zero costs for that line

#### Scenario: Finalize rejected for unpriced line ingredient

- **WHEN** a verified admin finalizes a plan that includes an ingredient with no resolvable cost
- **THEN** the system rejects finalize with a validation error and does not lock snapshot totals
