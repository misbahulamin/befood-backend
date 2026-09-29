## MODIFIED Requirements

### Requirement: Admin sets meal period when creating or updating a package

The system SHALL require a `meal_period` on meal package create and update with allowed values `lunch`, `dinner`, or `both`. The system MUST persist `meal_period` on `MealCategory` and MUST include it on admin meal list, detail, create, and update responses. Existing packages without a stored value MUST be treated as `both` after migration.

Package `meal_period` is the **upper bound** of periods a customer may select at subscribe time. A customer subscription MAY persist a narrower preference in `CustomerSubscription.meal_period_snapshot`, but MUST NOT exceed the package coverage.

#### Scenario: Create daily lunch package

- **WHEN** a verified admin creates a meal package with `meal_type=daily` and `meal_period=lunch`
- **THEN** the system stores the package and returns `meal_period` as `lunch`

#### Scenario: Create monthly both package

- **WHEN** a verified admin creates a meal package with `meal_type=monthly` and `meal_period=both`
- **THEN** the system stores the package and returns `meal_period` as `both`

#### Scenario: Missing meal period rejected

- **WHEN** a verified admin creates or updates a meal package without `meal_period`
- **THEN** the system rejects the request with a validation error on `meal_period`

#### Scenario: Invalid meal period rejected

- **WHEN** a verified admin submits `meal_period` with a value other than `lunch`, `dinner`, or `both`
- **THEN** the system rejects the request with a validation error

#### Scenario: Customer may narrow both package to lunch

- **WHEN** a customer subscribes to a package with `meal_period=both` choosing `meal_preference=lunch`
- **THEN** the package remains `both` while the subscription snapshot is `lunch`
