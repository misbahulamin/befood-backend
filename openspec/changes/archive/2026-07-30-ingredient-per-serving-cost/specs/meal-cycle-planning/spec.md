## ADDED Requirements

### Requirement: Plan lines require resolvable ingredient cost

The system SHALL reject adding or replacing a meal-cycle plan line when the referenced ingredient has no resolvable per-serving cost (neither a complete kg pricing pair nor a flat `cost_per_customer`). The error MUST identify the ingredient and MUST NOT treat missing cost as zero.

#### Scenario: Reject unpriced ingredient on plan line

- **WHEN** a verified admin adds a plan line for an ingredient that has neither kg pricing nor `cost_per_customer`
- **THEN** the system returns a validation error and does not create the line

#### Scenario: Accept priced ingredient on plan line

- **WHEN** a verified admin adds a plan line for an ingredient with a complete kg pair or a positive flat `cost_per_customer`
- **THEN** the system stores the line and includes it in subsequent summaries
