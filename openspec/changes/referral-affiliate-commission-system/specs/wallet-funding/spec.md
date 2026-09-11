## MODIFIED Requirements

### Requirement: Customer can withdraw from wallet with manual debit
The system SHALL allow an authenticated verified customer to withdraw by posting a positive monetary `amount` not exceeding the current **withdrawable** balance (`recharge_balance`). Withdraw MUST debit only `recharge_balance` (and therefore total `balance`) and MUST NOT reduce `commission_balance`. For the manual funding path, a successful withdraw request MUST create a pending or completed ledger transaction per the existing funding workflow with `type=withdraw`, `direction=debit`, and `method=manual`, and return updated wallet balances together with the transaction `public_id`. Insufficient withdrawable funds MUST be rejected without changing balances. Frozen wallets MUST reject withdraw. Referral commission balance MUST NOT be cash-withdrawable.

#### Scenario: Successful manual withdraw from recharge balance
- **WHEN** an authenticated verified customer with `recharge_balance` at least `500.00` posts a withdraw of `500.00`
- **THEN** the system accepts the withdraw against recharge funds, `recharge_balance` and total `balance` decrease by `500.00`, and `commission_balance` is unchanged

#### Scenario: Withdraw exceeds withdrawable balance but not total balance
- **WHEN** a customer has `recharge_balance` `50.00` and `commission_balance` `500.00` and posts a withdraw of `100.00`
- **THEN** the system rejects the operation and no wallet balances change

#### Scenario: Withdraw exceeds balance
- **WHEN** a customer posts a withdraw amount greater than the current withdrawable (`recharge_balance`) balance
- **THEN** the system rejects the operation and the balances remain unchanged

#### Scenario: Frozen wallet cannot withdraw
- **WHEN** a customer whose wallet `status` is `frozen` posts a withdraw
- **THEN** the system rejects the operation and does not debit any balance

## ADDED Requirements

### Requirement: Recharge credits increase only recharge balance
The system SHALL apply successful customer recharge credits exclusively to `recharge_balance` (and total `balance`). Recharge MUST NOT credit `commission_balance`. Admin Wallet customer-funding custody sync for recharge and withdraw MUST continue to apply only to real funding movements, not referral commission.

#### Scenario: Approved recharge increases recharge bucket
- **WHEN** a customer recharge of `200.00` completes successfully
- **THEN** `recharge_balance` and `balance` increase by `200.00` and `commission_balance` is unchanged
