# Spec Delta

## MODIFIED Requirements

### Requirement: Cron sends low wallet balance alert push on every meal-stop evaluation

When the wallet-balance threshold cron evaluates an active-subscriber customer and that customer’s spendable wallet balance (`spendable_balance` / `Wallet.balance`) is strictly less than the current `OrderWalletSettings.meal_stop_threshold`, the system SHALL send a customer push notification for that evaluation run. The system MUST allow multiple such pushes on the same calendar/business day when the cron runs more than once while the customer remains below the threshold. The system MUST NOT suppress this meal-stop-band warning push using `last_low_balance_reminder_on` or any other once-per-day idempotency key. Dry-run cron executions MUST NOT send the push. Customers without an active meal subscription MUST NOT receive this push from the cron path.

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

#### Scenario: Cancelled subscriber does not receive cron meal-stop push

- **WHEN** the threshold cron would otherwise see a cancelled (or never-subscribed) customer with spendable balance below `meal_stop_threshold`
- **THEN** the system does not send the Low Wallet Balance Alert push for that customer
