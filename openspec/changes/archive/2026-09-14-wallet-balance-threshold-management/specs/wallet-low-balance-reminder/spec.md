## ADDED Requirements

### Requirement: Reminder triggers below low-balance threshold

The system SHALL identify customers whose spendable wallet balance is strictly less than the configured `low_balance_reminder_threshold`, who are not meal-stopped under the meal-stop rules for the same run priority, and who have an active meal subscription. For each such customer the system MUST send a low-balance reminder at most once per Asia/Dhaka business day.

#### Scenario: Balance crosses below reminder threshold

- **WHEN** a subscribed customer’s spendable balance is `298.00` and `low_balance_reminder_threshold` is `300.00` and the customer is not meal-service blocked
- **THEN** the system sends a customer push notification and a branded email reminding them to recharge, including that meal service stops if balance falls below the meal-stop threshold

#### Scenario: Reminder not repeated same business day

- **WHEN** the threshold check runs again on the same Asia/Dhaka business day for a customer who already received a low-balance reminder that day
- **THEN** the system does not send another reminder push or email for that customer

#### Scenario: Balance at or above reminder threshold

- **WHEN** a subscribed customer’s spendable balance is greater than or equal to `low_balance_reminder_threshold`
- **THEN** the system does not send a low-balance reminder for that customer

### Requirement: Reminder delivery is best-effort

Low-balance reminder push and email failures MUST be logged and MUST NOT abort evaluation of remaining customers in the same run.

#### Scenario: Missing device tokens

- **WHEN** a customer qualifies for a reminder but has no registered FCM device tokens
- **THEN** the system still attempts email when an address is available, logs the push skip, and continues the batch
