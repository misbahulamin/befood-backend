# Spec Delta

## ADDED Requirements

### Requirement: Kitchen requirement includes Test Meal cooking headcount

Kitchen today-meal-requirement (and web alias) MUST include countable Test Meal units via the shared meal-demand service and scale ingredients from the consolidated final cooking count. Existing response field names MUST stay backward compatible. Customers MUST still be denied.

#### Scenario: Test Meal raises kitchen final cooking and ingredients

- **WHEN** a verified admin requests today-meal-requirement for a slot where subscription final cooking is `20` and one confirmed Test Meal exists for a package with published kg ingredients
- **THEN** final cooking count reflects `21` (or equivalent consolidated total) and ingredient kilograms scale using that consolidated count

#### Scenario: Customer still denied

- **WHEN** a verified customer calls kitchen today-meal-requirement after Test Meal shipping
- **THEN** the system returns `401` or `403`
