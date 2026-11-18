# Spec Delta

## MODIFIED Requirements

### Requirement: Reminder triggers below low-balance threshold

The system SHALL identify customers whose spendable wallet balance is strictly less than the configured `low_balance_reminder_threshold`, who are not meal-stopped under the meal-stop rules for the same run priority, and who have an active meal subscription. For each such customer the system MUST send a low-balance reminder at most once per Asia/Dhaka business day. Customers whose subscription is cancelled, or who have never had a meal subscription, MUST NOT receive a low-balance reminder.

#### Scenario: Balance crosses below reminder threshold

- **WHEN** a subscribed customer’s spendable balance is `298.00` and `low_balance_reminder_threshold` is `300.00` and the customer is not meal-service blocked
- **THEN** the system sends a customer push notification and a branded email reminding them to recharge, including that meal service stops if balance falls below the meal-stop threshold

#### Scenario: Reminder not repeated same business day

- **WHEN** the threshold check runs again on the same Asia/Dhaka business day for a customer who already received a low-balance reminder that day
- **THEN** the system does not send another reminder push or email for that customer

#### Scenario: Balance at or above reminder threshold

- **WHEN** a subscribed customer’s spendable balance is greater than or equal to `low_balance_reminder_threshold`
- **THEN** the system does not send a low-balance reminder for that customer

#### Scenario: Cancelled or never-subscribed customer not reminded

- **WHEN** a customer has no active meal subscription and spendable balance is strictly below `low_balance_reminder_threshold`
- **THEN** the system does not send a low-balance reminder push or email for that customer
