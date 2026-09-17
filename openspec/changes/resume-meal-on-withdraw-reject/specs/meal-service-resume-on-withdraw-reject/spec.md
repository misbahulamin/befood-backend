## ADDED Requirements

### Requirement: Rejected withdraw resumes meal service when restored balance meets meal-stop threshold

When a verified admin successfully rejects a pending customer wallet withdraw, the system SHALL release the reserved spendable balance (credit the reserved amount back to the customer wallet) and then evaluate low-balance meal-stop resume by calling `maybe_resume_after_wallet_credit` with that customer’s `CustomerProfile`. Resume MUST use the same spendable balance source as recharge approve and the wallet-threshold cron (`spendable_balance` over `Wallet.balance`) and the live `OrderWalletSettings.meal_stop_threshold`. If the customer is blocked and post-reject spendable balance is greater than or equal to that threshold, the system MUST set `meal_service_blocked_low_balance` to `false` and `meal_service_blocked_at` to `null` as part of the same successful reject outcome. If post-reject balance remains below the threshold, meal-stop block fields MUST remain unchanged by the resume evaluation. Withdraw approve MUST NOT clear meal-stop via this path. Auto meal delivery skip-on-block behavior MUST remain unchanged. The system MUST NOT send a dedicated “meal service restored” customer notification solely because withdraw reject cleared meal-stop.

#### Scenario: Withdraw reservation caused block and reject restores above threshold

- **WHEN** a customer has spendable balance `200.00`, `meal_stop_threshold` is `150.00`, the customer submits a pending withdraw of `100.00` (spendable becomes `100.00`), `meal_service_blocked_low_balance` is later `true`, and a verified admin rejects that pending withdraw
- **THEN** the wallet spendable balance returns to `200.00`, `meal_service_blocked_low_balance` is `false`, and `meal_service_blocked_at` is `null`

#### Scenario: Reject restores balance but customer remains below threshold

- **WHEN** a customer is meal-stop blocked with spendable balance `50.00` after a pending withdraw reservation, `meal_stop_threshold` is `150.00`, and rejecting the withdraw restores only to `120.00`
- **THEN** the wallet balance becomes `120.00` and `meal_service_blocked_low_balance` remains `true`

#### Scenario: Unblocked customer withdraw reject leaves flags unchanged

- **WHEN** a customer has `meal_service_blocked_low_balance` set to `false` and a verified admin rejects a pending withdraw
- **THEN** the reserved amount is released and meal-stop block fields are left unchanged by the resume evaluation

#### Scenario: Latest meal-stop threshold is used at withdraw reject

- **WHEN** a customer is meal-stop blocked, an admin raises `meal_stop_threshold`, and a verified admin rejects a pending withdraw such that post-reject balance is still below the new threshold
- **THEN** `meal_service_blocked_low_balance` remains `true`

#### Scenario: Withdraw approve does not resume meal service

- **WHEN** a verified admin approves a pending withdraw for a meal-stop-blocked customer
- **THEN** `meal_service_blocked_low_balance` is not cleared by withdraw approval

#### Scenario: Resume on withdraw reject does not send meal-restored customer notification

- **WHEN** a verified admin rejects a withdraw that clears meal-stop
- **THEN** the system does not send a dedicated “meal service restored” customer push or email for that restore

### Requirement: Admin withdraw reject response reports meal service restore outcome

On a successful admin funding reject response for a withdraw, the system SHALL include a boolean field `meal_service_restored` that equals the boolean returned by `maybe_resume_after_wallet_credit` for that reject (or `false` when resume is not evaluated). The field MUST be `true` only when that reject cleared the customer’s low-balance meal-stop block, and `false` otherwise (including when the customer was not blocked, remained below threshold after reservation release, or the rejected request is a recharge). Existing reject success fields MUST remain available; clients that ignore unknown fields MUST remain compatible. Frontend clients MUST NOT compute meal-stop resume themselves. No database migration is required for this field.

#### Scenario: Withdraw reject response indicates meal service restored

- **WHEN** a verified admin rejects a pending withdraw that clears meal-stop for a previously blocked customer
- **THEN** the HTTP success response includes `meal_service_restored` set to `true`

#### Scenario: Withdraw reject response indicates meal service not restored

- **WHEN** a verified admin rejects a pending withdraw for a blocked customer whose post-reject balance remains below `meal_stop_threshold`
- **THEN** the HTTP success response includes `meal_service_restored` set to `false`

#### Scenario: Recharge reject does not claim meal service restored

- **WHEN** a verified admin rejects a pending recharge
- **THEN** the HTTP success response includes `meal_service_restored` set to `false` and meal-stop block fields are not cleared by recharge rejection
