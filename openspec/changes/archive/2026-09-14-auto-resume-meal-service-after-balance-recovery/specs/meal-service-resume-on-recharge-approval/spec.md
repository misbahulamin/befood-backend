## ADDED Requirements

### Requirement: Approved recharge resumes meal service when balance meets meal-stop threshold

When a verified admin successfully approves a pending customer wallet recharge and the customer wallet is credited by the approved amount, the system SHALL evaluate low-balance meal-stop resume by calling `maybe_resume_after_wallet_credit` with that customer’s `CustomerProfile`. The helper MUST return a boolean indicating whether the block was cleared. Resume MUST use the same spendable balance source as the wallet-threshold cron (`spendable_balance` over `Wallet.balance`) and the live `OrderWalletSettings.meal_stop_threshold`. If the customer is blocked and post-credit spendable balance is greater than or equal to that threshold, the system MUST set `meal_service_blocked_low_balance` to `false` and `meal_service_blocked_at` to `null` as part of the same successful approval outcome. Pending or rejected recharges MUST NOT change meal-stop block fields. Auto meal delivery skip-on-block behavior MUST remain unchanged by this approval path. The system MUST NOT send a new customer notification solely because meal service was restored; existing recharge-approved notifications MAY still run.

#### Scenario: Blocked customer recharges enough to clear meal-stop

- **WHEN** a customer has spendable balance `100.00`, `meal_service_blocked_low_balance` is `true`, `meal_stop_threshold` is `150.00`, and a verified admin approves a pending recharge of `100.00`
- **THEN** the wallet balance becomes `200.00`, `meal_service_blocked_low_balance` is `false`, and `meal_service_blocked_at` is `null`

#### Scenario: Blocked customer recharges but remains below threshold

- **WHEN** a customer has spendable balance `100.00`, `meal_service_blocked_low_balance` is `true`, `meal_stop_threshold` is `150.00`, and a verified admin approves a pending recharge of `20.00`
- **THEN** the wallet balance becomes `120.00` and `meal_service_blocked_low_balance` remains `true`

#### Scenario: Unblocked customer recharge does not alter meal-stop flags

- **WHEN** a customer has `meal_service_blocked_low_balance` set to `false` and a verified admin approves a pending recharge
- **THEN** the wallet balance increases by the approved amount and the meal-stop block fields are left unchanged by the resume evaluation

#### Scenario: Latest meal-stop threshold is used at approval

- **WHEN** a customer is meal-stop blocked with balance `100.00`, an admin later raises `meal_stop_threshold` from `150.00` to `200.00`, and a verified admin then approves a pending recharge of `80.00` (new balance `180.00`)
- **THEN** `meal_service_blocked_low_balance` remains `true` because `180.00` is below the current threshold `200.00`

#### Scenario: Pending recharge does not resume meal service

- **WHEN** a blocked customer submits a pending recharge that has not been approved
- **THEN** the wallet spendable balance and `meal_service_blocked_low_balance` remain unchanged by that pending request

#### Scenario: Rejected recharge does not resume meal service

- **WHEN** a verified admin rejects a pending recharge for a meal-stop-blocked customer
- **THEN** the wallet balance is not credited and `meal_service_blocked_low_balance` remains `true`

#### Scenario: Resume does not send a meal-restored customer notification

- **WHEN** a verified admin approves a recharge that clears meal-stop
- **THEN** the system does not send a dedicated “meal service restored” customer push or email for that restore (recharge-approved notifications may still be sent)

### Requirement: Admin approve response reports meal service restore outcome

On a successful admin funding approve response for a recharge, the system SHALL include a boolean field `meal_service_restored` that equals the boolean returned by `maybe_resume_after_wallet_credit` for that approval (or `false` when resume is not evaluated). The field MUST be `true` only when that approval cleared the customer’s low-balance meal-stop block, and `false` otherwise (including when the customer was not blocked, remained below threshold after credit, or the approved request is a withdraw). Existing approve success fields MUST remain available; adding `meal_service_restored` MUST NOT break clients that ignore unknown fields. Frontend clients MUST NOT compute meal-stop resume themselves. No database migration is required for this field.

#### Scenario: Approve response indicates meal service restored

- **WHEN** a verified admin approves a pending recharge that clears meal-stop for a previously blocked customer
- **THEN** the HTTP success response includes `meal_service_restored` set to `true`

#### Scenario: Approve response indicates meal service not restored

- **WHEN** a verified admin approves a pending recharge for a blocked customer whose post-credit balance remains below `meal_stop_threshold`
- **THEN** the HTTP success response includes `meal_service_restored` set to `false`

#### Scenario: Withdraw approve does not claim meal service restored

- **WHEN** a verified admin successfully approves a pending withdraw
- **THEN** the HTTP success response includes `meal_service_restored` set to `false` and meal-stop block fields are not cleared by withdraw approval
