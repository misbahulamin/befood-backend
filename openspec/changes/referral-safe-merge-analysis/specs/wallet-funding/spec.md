## MODIFIED Requirements

### Requirement: Customer can withdraw from wallet with manual debit
The system SHALL allow an authenticated verified customer to withdraw by posting a positive monetary `amount` not exceeding the current **withdrawable** balance (`recharge_balance`). Withdraw MUST debit only `recharge_balance` (and therefore total `balance`) and MUST NOT reduce `commission_balance`. For the manual funding path, a successful withdraw request MUST create a pending or completed ledger transaction per the existing funding workflow with `type=withdraw`, `direction=debit`, and `method=manual`, and return updated wallet balances together with the transaction `public_id`. Insufficient withdrawable funds MUST be rejected without changing balances. Frozen wallets MUST reject withdraw. Referral commission balance MUST NOT be cash-withdrawable. Production-hotfix Admin Wallet custody sync and meal-service resume behavior on recharge approve MUST continue to apply to real funding movements, not referral commission.

#### Scenario: Successful manual withdraw from recharge bucket
- **WHEN** an authenticated verified customer with `recharge_balance` at least `500.00` posts a withdraw of `500.00`
- **THEN** the system responds with success, `recharge_balance` and `balance` decrease by `500.00`, `commission_balance` is unchanged, and a `withdraw` transaction with `method=manual` exists

#### Scenario: Withdraw blocked when only commission remains
- **WHEN** a customer has `recharge_balance` `0.00` and `commission_balance` `100.00` and posts a withdraw of `50.00`
- **THEN** the system rejects the operation and all balances remain unchanged

#### Scenario: Withdraw exceeds withdrawable balance
- **WHEN** a customer posts a withdraw amount greater than `recharge_balance` even if total `balance` is larger
- **THEN** the system rejects the operation and balances remain unchanged

#### Scenario: Frozen wallet cannot withdraw
- **WHEN** a customer whose wallet `status` is `frozen` posts a withdraw
- **THEN** the system rejects the operation and does not debit any balance

## ADDED Requirements

### Requirement: Recharge credits only the recharge bucket
The system SHALL apply successful customer recharge credits exclusively to `recharge_balance` (and total `balance`). Recharge MUST NOT credit `commission_balance`. Admin Wallet customer-funding custody sync for recharge and withdraw MUST continue to apply only to real funding movements, not referral commission.

#### Scenario: Approved recharge increases recharge bucket
- **WHEN** a pending recharge of `200.00` is approved
- **THEN** `recharge_balance` and `balance` increase by `200.00` and `commission_balance` is unchanged

### Requirement: Live provider recharge refs remain unique after dual-bucket integration
Provider recharge uniqueness checks and the database UniqueConstraint MUST continue to consider only live statuses (`pending`, `completed`) after dual-bucket integration, matching production-hotfix semantics.

#### Scenario: Provider ref check ignores failed rows
- **WHEN** `_provider_ref_taken` (or equivalent) evaluates a method/ref pair that exists only on a `failed` recharge
- **THEN** the check reports the ref as available for a new live recharge
