## ADDED Requirements

### Requirement: Meal service block below meal-stop threshold

The system SHALL set a customer-level meal-service block when a subscribed customer’s spendable wallet balance is strictly less than the configured `meal_stop_threshold`. While blocked, automated meal delivery processing for that customer MUST NOT run. Manual admin mark-delivery and existing customer meal-off flows MUST remain available.

#### Scenario: Balance falls below meal-stop threshold

- **WHEN** a subscribed customer’s spendable balance is `170.00` and `meal_stop_threshold` is `200.00`
- **THEN** the system marks the customer’s meal service as blocked for low balance and excludes them from auto meal-delivery eligibility

#### Scenario: Auto-delivery skips blocked customer

- **WHEN** auto meal delivery runs for a meal period and a customer is meal-service blocked for low balance with `scheduled` slots that day
- **THEN** those slots are not auto-marked delivered by the cron path

#### Scenario: Admin can still mark delivery manually

- **WHEN** a verified admin marks a blocked customer’s scheduled delivery as delivered through the existing admin mark API
- **THEN** the mark-delivery and wallet charge path proceeds under existing meal payment rules

### Requirement: Notify customer on meal stop

When meal service becomes blocked for low balance, the system SHALL notify the customer via push (when tokens exist) and branded email that meal service has stopped until they recharge.

#### Scenario: Stop notification on transition

- **WHEN** a customer transitions from unblocked to blocked because balance is below `meal_stop_threshold`
- **THEN** the system sends a meal-stop push and email explaining that recharging is required to resume meals

### Requirement: Auto-resume when balance recovers

The system SHALL clear the low-balance meal-service block when the customer’s spendable balance is greater than or equal to `meal_stop_threshold`, so future automated meal processing can resume without requiring a new subscription.

#### Scenario: Resume after recharge

- **WHEN** a blocked customer’s spendable balance becomes `250.00` and `meal_stop_threshold` is `200.00`
- **THEN** the system clears the meal-service block and subsequent auto-delivery eligibility includes that customer again (subject to other live-delivery rules)
