## ADDED Requirements

### Requirement: Successful meal charge evaluates meal-stop threshold immediately

After a successful meal-delivery wallet debit that reduces the customer’s spendable balance, the system SHALL evaluate that customer against the live `OrderWalletSettings.meal_stop_threshold` using the same spendable balance source as the wallet-threshold cron (`spendable_balance` / wallet `balance`). If spendable balance is strictly less than `meal_stop_threshold`, the system MUST set `CustomerProfile.meal_service_blocked_low_balance` to `true` (and set `meal_service_blocked_at` when newly blocked) before relying on the next scheduled 08:00/20:00 Asia/Dhaka wallet-threshold cron. This evaluation MUST run for both auto-delivery charges and operator mark-delivered charges. Idempotent re-attach of an already-charged delivery that does not debit again MUST NOT be required to re-apply the block, but a real debit in this request MUST evaluate after the post-debit balance is visible. Notification side effects on newly blocked customers MUST follow existing meal-stop notify rules and MUST NOT roll back a successful charge if notify fails.

#### Scenario: Lunch charge drops balance below meal-stop and blocks immediately

- **WHEN** a customer is not meal-stop blocked, `meal_stop_threshold` is `100.00`, spendable balance is `150.00`, and a lunch delivery is successfully charged for `60.00` (post-debit balance `90.00`)
- **THEN** `meal_service_blocked_low_balance` is `true` without waiting for the 20:00 wallet-threshold job

#### Scenario: Charge that leaves balance at or above threshold does not block

- **WHEN** a customer is not blocked, `meal_stop_threshold` is `100.00`, spendable balance is `200.00`, and a delivery is successfully charged for `50.00` (post-debit balance `150.00`)
- **THEN** `meal_service_blocked_low_balance` remains `false`

#### Scenario: Operator mark-delivered also triggers evaluation

- **WHEN** an authorized operator marks a `scheduled` delivery `delivered` and the meal-payment debit succeeds with post-debit balance strictly below `meal_stop_threshold`
- **THEN** the customer is meal-stop blocked immediately under the same rules as auto-delivery

#### Scenario: Notify failure does not undo charge or block write

- **WHEN** post-charge meal-stop evaluation newly blocks a customer but meal-stop notification delivery fails
- **THEN** the meal-payment debit and `meal_service_blocked_low_balance=true` remain committed

### Requirement: Twice-daily wallet-threshold cron remains complementary

The system MUST continue to run the existing Asia/Dhaka 08:00 and 20:00 wallet-threshold checks (`check_wallet_balance_thresholds`) for meal-stop, reminder, resume, and admin summary behaviors that are not covered by a meal-payment debit. Post-charge meal-stop evaluation MUST NOT replace or remove that cron.

#### Scenario: Evening cron still evaluates customers without a same-day meal charge

- **WHEN** an active subscriber’s spendable balance falls below `meal_stop_threshold` without a successful meal-payment debit since the last cron run
- **THEN** the 08:00 or 20:00 wallet-threshold job still applies meal-stop blocking according to existing cron rules
