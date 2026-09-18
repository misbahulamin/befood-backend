## MODIFIED Requirements

### Requirement: Meal service block below meal-stop threshold

The system SHALL set a customer-level meal-service block when a subscribed customer’s spendable wallet balance is strictly less than the configured `meal_stop_threshold`. While blocked, automated meal delivery processing for that customer MUST NOT run, and deliveryman field mark-delivered MUST be rejected under the same exclusion. Manual **admin/operator** mark-delivery and existing customer meal-off flows MUST remain available.

#### Scenario: Balance falls below meal-stop threshold

- **WHEN** a subscribed customer’s spendable balance is `170.00` and `meal_stop_threshold` is `200.00`
- **THEN** the system marks the customer’s meal service as blocked for low balance and excludes them from auto meal-delivery eligibility

#### Scenario: Auto-delivery skips blocked customer

- **WHEN** auto meal delivery runs for a meal period and a customer is meal-service blocked for low balance with `scheduled` slots that day
- **THEN** those slots are not auto-marked delivered by the cron path

#### Scenario: Deliveryman cannot mark blocked customer

- **WHEN** a verified deliveryman attempts to mark a meal-stop blocked customer’s scheduled delivery as delivered
- **THEN** the mark is rejected, the delivery is not transitioned to `delivered` by the deliveryman path, and no meal-payment debit is created from that attempt

#### Scenario: Admin can still mark delivery manually

- **WHEN** a verified admin marks a blocked customer’s scheduled delivery as delivered through the existing admin mark API
- **THEN** the mark-delivery and wallet charge path proceeds under existing meal payment rules
