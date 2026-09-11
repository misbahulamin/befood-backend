## ADDED Requirements

### Requirement: Wallet summary withdrawable balance respects meal-stop threshold
Customer wallet summary responses MUST expose `withdrawable_balance` as `max(0, recharge_balance - meal_stop_threshold)` and MUST expose `meal_stop_threshold` from current order wallet settings. The field `recharge_balance` MUST remain the full recharge bucket (including amounts that are reserved as meal-stop floor and therefore not withdrawable).

#### Scenario: Withdrawable is less than recharge when threshold is positive
- **WHEN** an authenticated verified customer with `recharge_balance` `420.00` and `meal_stop_threshold` `100.00` requests their wallet
- **THEN** the response includes `recharge_balance` `420.00`, `withdrawable_balance` `320.00`, and `meal_stop_threshold` `100.00`

#### Scenario: Withdrawable is zero at the floor
- **WHEN** an authenticated verified customer with `recharge_balance` `80.00` and `meal_stop_threshold` `100.00` requests their wallet
- **THEN** the response includes `withdrawable_balance` `0.00`
