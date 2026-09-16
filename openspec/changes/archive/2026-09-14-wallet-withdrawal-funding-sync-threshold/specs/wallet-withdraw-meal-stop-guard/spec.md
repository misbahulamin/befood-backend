## ADDED Requirements

### Requirement: Maximum withdrawable preserves meal_stop_threshold from recharge balance
The system SHALL compute the customer maximum withdrawable amount as `max(0, recharge_balance - meal_stop_threshold)` using the current `OrderWalletSettings.meal_stop_threshold`. Commission balance MUST NOT increase the withdrawable amount. When `recharge_balance` is less than or equal to `meal_stop_threshold`, maximum withdrawable MUST be `0.00`.

#### Scenario: Partial recharge above threshold is withdrawable
- **WHEN** a wallet has `recharge_balance` `420.00`, any `commission_balance`, and `meal_stop_threshold` is `100.00`
- **THEN** maximum withdrawable is `320.00`

#### Scenario: Recharge at or below threshold blocks withdraw
- **WHEN** a wallet has `recharge_balance` `100.00` and `meal_stop_threshold` is `100.00`
- **THEN** maximum withdrawable is `0.00`

#### Scenario: Commission does not increase withdrawable
- **WHEN** a wallet has `recharge_balance` `150.00`, `commission_balance` `500.00`, and `meal_stop_threshold` is `100.00`
- **THEN** maximum withdrawable is `50.00`

### Requirement: Withdraw request enforces meal-stop floor before reservation
When an authenticated verified customer submits a withdraw request, the system MUST reject the request without reserving funds if `amount` exceeds `max(0, recharge_balance - meal_stop_threshold)`. Successful requests MUST continue to debit only `recharge_balance` (recharge-only strategy) and MUST leave `commission_balance` unchanged. The system MUST continue to create a pending withdraw reservation at request time and MUST NOT debit Admin Wallet custody until approve.

#### Scenario: Allowed amount under the floor succeeds
- **WHEN** a verified customer with `recharge_balance` `420.00` and `meal_stop_threshold` `100.00` posts a withdraw of `300.00`
- **THEN** the system accepts the request, reserves `300.00` from `recharge_balance`, and leaves at least `100.00` in `recharge_balance` after reservation

#### Scenario: Amount above maximum withdrawable is rejected
- **WHEN** a verified customer with `recharge_balance` `420.00` and `meal_stop_threshold` `100.00` posts a withdraw of `400.00`
- **THEN** the system rejects the request without changing balances and does not create a new withdraw reservation

#### Scenario: Zero maximum withdrawable rejects any positive withdraw
- **WHEN** a verified customer with `recharge_balance` `100.00` and `meal_stop_threshold` `100.00` posts a withdraw of `1.00`
- **THEN** the system rejects the request without changing balances

### Requirement: Wallet summary exposes threshold-aware withdrawable balance
Customer wallet summary responses MUST expose `withdrawable_balance` equal to `max(0, recharge_balance - meal_stop_threshold)` and MUST continue to expose `meal_stop_threshold` so clients can render remaining meal-service reserve messaging. `recharge_balance` and `commission_balance` MUST remain separately visible and MUST NOT be conflated with withdrawable amount.

#### Scenario: Wallet GET returns computed withdrawable
- **WHEN** an authenticated verified customer with `recharge_balance` `420.00` and settings `meal_stop_threshold` `100.00` requests their wallet
- **THEN** the response includes `withdrawable_balance` `320.00` and `meal_stop_threshold` `100.00`
