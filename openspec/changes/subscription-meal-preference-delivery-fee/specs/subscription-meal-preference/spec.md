## ADDED Requirements

### Requirement: Subscribe persists customer meal preference

The system SHALL accept an optional `meal_preference` of `lunch`, `dinner`, or `both` on `POST /api/v1/subscriptions/`. When provided, the system MUST validate it against the package `MealCategory.meal_period` coverage and MUST persist the effective value on `CustomerSubscription.meal_period_snapshot`. The preference MUST be treated as the permanent subscription meal configuration for all subsequent delivery generation.

#### Scenario: Lunch preference on both package

- **WHEN** a verified customer subscribes to a package with `meal_period=both` with `meal_preference=lunch`
- **THEN** the subscription stores `meal_period_snapshot=lunch` and only lunch delivery slots are generated for the rolling horizon

#### Scenario: Dinner preference on both package

- **WHEN** a verified customer subscribes to a package with `meal_period=both` with `meal_preference=dinner`
- **THEN** the subscription stores `meal_period_snapshot=dinner` and only dinner delivery slots are generated

#### Scenario: Both preference

- **WHEN** a verified customer subscribes with `meal_preference=both` to a both package
- **THEN** lunch and dinner slots are generated for each eligible service date

#### Scenario: Preference outside package coverage rejected

- **WHEN** a customer requests `meal_preference=both` (or the opposite single period) for a lunch-only or dinner-only package
- **THEN** the system rejects with a validation error (`MEAL_PREFERENCE_NOT_SUPPORTED`) and creates no subscription

#### Scenario: Invalid preference rejected

- **WHEN** `meal_preference` is not one of `lunch`, `dinner`, `both`
- **THEN** the system rejects with `INVALID_MEAL_PREFERENCE`

### Requirement: Legacy clients may omit meal preference

When `meal_preference` is omitted or null, the system MUST fall back to the package `meal_period` (previous production behavior) so installed web/mobile clients continue to subscribe successfully during the compatibility window.

#### Scenario: Old client omits preference on both package

- **WHEN** a client posts only `plan_public_id` for a package with `meal_period=both`
- **THEN** the subscription is created with `meal_period_snapshot=both` and both periods are scheduled

### Requirement: Subscription quantity is canonical

The system SHALL persist `CustomerSubscription.quantity` as a positive integer (minimum 1). Subscribe MAY accept `quantity`; when omitted the system MUST default to `1`. Quantity MUST be the only source used for both-tier delivery-fee calculation for that subscription.

#### Scenario: Explicit quantity stored

- **WHEN** a customer subscribes with `quantity=2`
- **THEN** the subscription stores `quantity=2` and APIs return that value

#### Scenario: Invalid quantity rejected

- **WHEN** `quantity` is less than 1 or not an integer
- **THEN** the system rejects with `INVALID_QUANTITY`

#### Scenario: Existing rows receive default quantity

- **WHEN** the additive quantity migration runs
- **THEN** existing subscription rows have `quantity=1` and their `meal_period_snapshot` values are unchanged

### Requirement: All delivery generation respects preference

`ensure_subscription_deliveries`, daily ensure command, and post-publish ensure paths MUST generate slots only for periods returned by `periods_for_meal_period(subscription.meal_period_snapshot)`. They MUST NOT create dinner rows for lunch-only subscriptions or lunch rows for dinner-only subscriptions.

#### Scenario: Rolling horizon backfill respects lunch-only

- **WHEN** ensure runs for an active lunch-only subscription
- **THEN** new rows are lunch-only; no dinner rows are created

#### Scenario: Existing both subscriptions unchanged

- **WHEN** ensure runs for an existing subscription with `meal_period_snapshot=both`
- **THEN** lunch and dinner continue to be generated as before

### Requirement: Subscribe response exposes preference, quantity, and fee summary

Customer subscription create/current/detail responses MUST include `meal_period_snapshot`, `quantity`, `monthly_delivery_fee`, and `fee_rule_code` derived from the canonical fee calculator.

#### Scenario: Create response includes fee fields

- **WHEN** subscribe succeeds with preference `lunch` and quantity `1`
- **THEN** the `201` body includes `meal_period_snapshot=lunch`, `quantity=1`, and `monthly_delivery_fee` equal to the lunch fee amount
