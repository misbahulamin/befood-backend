## ADDED Requirements

### Requirement: Cron sends low wallet balance alert push on every meal-stop evaluation

When the wallet-balance threshold cron evaluates a customer and that customer’s spendable wallet balance (`spendable_balance` / `Wallet.balance`) is strictly less than the current `OrderWalletSettings.meal_stop_threshold`, the system SHALL send a customer push notification for that evaluation run. The system MUST allow multiple such pushes on the same calendar/business day when the cron runs more than once while the customer remains below the threshold. The system MUST NOT suppress this meal-stop-band warning push using `last_low_balance_reminder_on` or any other once-per-day idempotency key. Dry-run cron executions MUST NOT send the push.

#### Scenario: Morning cron sends low balance alert and blocks meal service

- **WHEN** the threshold cron runs for a subscribed customer with spendable balance `100.00` and `meal_stop_threshold` `150.00`
- **THEN** the system sends the Low Wallet Balance Alert push and ensures `meal_service_blocked_low_balance` is `true`

#### Scenario: Night cron sends another alert while still below threshold

- **WHEN** the same customer still has spendable balance below `meal_stop_threshold` on a later threshold cron run the same day
- **THEN** the system sends another Low Wallet Balance Alert push without requiring a new transition into the blocked state

#### Scenario: Above meal-stop after recharge does not send meal-stop-band alert

- **WHEN** a customer’s spendable balance is greater than or equal to `meal_stop_threshold` during a threshold cron run (including after a successful recharge resume)
- **THEN** the system does not send the Low Wallet Balance Alert push for the meal-stop band on that evaluation

#### Scenario: Still-blocked customer continues to receive alerts on later runs

- **WHEN** a customer remains meal-stop blocked with balance still below `meal_stop_threshold` across subsequent non-dry-run cron evaluations
- **THEN** each such evaluation sends the Low Wallet Balance Alert push

### Requirement: Low Wallet Balance Alert push copy

The meal-stop-band warning push SHALL use title `Low Wallet Balance Alert` and body text that greets the customer by full name and warns that the wallet balance is low, that they should recharge soon to continue receiving meals, and that meal service will be paused if balance remains low. Push delivery failures MUST be logged and MUST NOT roll back meal-stop block application for that customer.

#### Scenario: Push uses required title and personalized body

- **WHEN** the cron sends a Low Wallet Balance Alert for customer display name `Rahim Ahmed`
- **THEN** the push title is `Low Wallet Balance Alert` and the body includes `Hi Rahim Ahmed, your current wallet balance is low. Please recharge your wallet soon to continue receiving your meals. If your balance remains low, your meal service will be paused.`

### Requirement: Meal-stop block remains independent of the warning push

When spendable balance is strictly below `meal_stop_threshold`, the system SHALL continue to set or keep `meal_service_blocked_low_balance` according to existing meal-stop rules so automated meal delivery stays paused. Sending or failing the Low Wallet Balance Alert push MUST NOT replace or remove that block behavior. Auto meal delivery’s check of `meal_service_blocked_low_balance` MUST remain unchanged.

#### Scenario: Block applies even if push cannot be delivered

- **WHEN** balance is below `meal_stop_threshold` and FCM/push delivery fails during the cron evaluation
- **THEN** `meal_service_blocked_low_balance` is still `true` (or newly set) and automated meal delivery remains subject to the existing skip-on-block rule
