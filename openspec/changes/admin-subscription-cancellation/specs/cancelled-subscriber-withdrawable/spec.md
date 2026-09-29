## ADDED Requirements

### Requirement: Active subscribers keep meal-stop withdraw floor

While a customer has an active meal subscription, maximum withdrawable balance MUST remain `max(0, recharge_balance − meal_stop_threshold)` quantized to two decimal places. Commission balance MUST NOT contribute to withdrawable balance. `GET` wallet representations and `request_withdraw` validation MUST use the same computation.

#### Scenario: Active subscriber cannot withdraw through meal-stop floor

- **WHEN** an active subscriber has recharge balance `300.00` and `meal_stop_threshold` `100.00`
- **THEN** `withdrawable_balance` is `200.00` and a withdraw request above `200.00` is rejected

### Requirement: Cancelled customers drop meal-stop floor but retain finalized meal liability

When a customer has no active subscription, maximum withdrawable balance MUST NOT subtract `meal_stop_threshold`. Instead it MUST be `max(0, recharge_balance − finalized_meal_liability)` where `finalized_meal_liability` is the sum of estimated meal charges for that customer’s still-`scheduled` deliveries whose meal-off cutoff has already passed, priced from the same published menu slot final price source used by meal delivery charging. Soft-skipped or delivered meals MUST NOT add liability. Pending withdraw reservations that already reduced `recharge_balance` MUST continue to be reflected only through the reduced balance (no second reservation layer).

#### Scenario: After cancel with preserved dinner liability

- **WHEN** a customer’s subscription is cancelled, recharge balance is `300.00`, meal-stop threshold is `100.00`, and one preserved past-cutoff `scheduled` dinner has published slot price `80.00`
- **THEN** `withdrawable_balance` is `220.00` (not `200.00` and not `300.00`)

#### Scenario: After cancel with no preserved scheduled meals

- **WHEN** a customer has no active subscription, no past-cutoff `scheduled` deliveries, and recharge balance `300.00`
- **THEN** `withdrawable_balance` equals `300.00` regardless of a positive `meal_stop_threshold`

#### Scenario: Withdraw validation matches displayed withdrawable

- **WHEN** a cancelled customer’s wallet shows `withdrawable_balance` `220.00`
- **THEN** `request_withdraw` accepts `220.00` and rejects amounts above `220.00` using the same formula

#### Scenario: Liability clears after preserved meal is charged

- **WHEN** the preserved dinner is later delivered and charged for `80.00`, leaving recharge balance `220.00` with no remaining past-cutoff `scheduled` liability
- **THEN** `withdrawable_balance` becomes `220.00` (full remaining recharge)

### Requirement: Clients consume backend withdrawable fields

API responses that expose wallet withdraw eligibility MUST include the computed `withdrawable_balance` from the shared backend helper. Clients MUST treat that field as authoritative and MUST NOT recompute eligibility by hardcoding `wallet_balance − meal_stop_threshold` or `wallet_balance − meal_price`.

#### Scenario: Wallet payload exposes canonical withdrawable

- **WHEN** a verified customer fetches their wallet after subscription cancel with a finalized meal liability
- **THEN** the response includes `withdrawable_balance` equal to the shared backend computation for cancelled subscribers
