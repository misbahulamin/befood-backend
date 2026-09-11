## MODIFIED Requirements

### Requirement: Customer can withdraw from wallet with manual debit
The system SHALL allow an authenticated verified customer to submit a withdraw by posting a positive monetary `amount` that passes shared amount validation and does not exceed `max(0, recharge_balance - meal_stop_threshold)`. Successful withdraw submission MUST debit only `recharge_balance` (and total `balance`) immediately as a reservation, MUST leave `commission_balance` unchanged, MUST create a ledger transaction with `type=withdraw`, `direction=debit`, `status=pending`, and `method=manual`, and MUST NOT mark the withdraw `completed` or debit Admin Wallet custody at submit time. Insufficient recharge-after-threshold funds MUST be rejected without changing balances. Frozen wallets MUST reject withdraw.

#### Scenario: Successful pending withdraw reserves recharge only
- **WHEN** an authenticated verified customer with `recharge_balance` at least `320.00`, `meal_stop_threshold` `100.00`, and sufficient headroom posts a withdraw of `300.00` while manual funding is enabled
- **THEN** the system responds with success, a `withdraw` transaction exists with `status=pending` and `method=manual`, `recharge_balance` and `balance` decrease by `300.00`, and `commission_balance` is unchanged

#### Scenario: Withdraw exceeds meal-stop-aware maximum
- **WHEN** a customer posts a withdraw amount greater than `max(0, recharge_balance - meal_stop_threshold)`
- **THEN** the system rejects the operation and all wallet balances remain unchanged

#### Scenario: Withdraw cannot use commission balance
- **WHEN** a customer has `recharge_balance` `50.00`, `commission_balance` `400.00`, and `meal_stop_threshold` `100.00`
- **THEN** any positive withdraw request is rejected because maximum withdrawable is `0.00`

#### Scenario: Frozen wallet cannot withdraw
- **WHEN** a customer whose wallet `status` is `frozen` posts a withdraw
- **THEN** the system rejects the operation and does not debit the balance

### Requirement: Successful withdraw syncs Admin Wallet custody
When a customer withdraw is approved and becomes completed, the system MUST debit the platform Admin Wallet for the same amount as a completed custody transaction with type `customer_withdraw` (direction `debit`), idempotent per customer wallet transaction, inside the same database transaction as marking the customer withdraw completed. Creating a pending withdraw MUST NOT debit Admin Wallet custody. The system MUST NOT create, reverse, or rewrite Admin Wallet `customer_funding` credit rows as the withdraw outflow mechanism. If Admin Wallet cash balance cannot cover the debit at approve time, the system MUST respond `409 Conflict`, MUST leave the withdraw `pending`, MUST leave the customer reservation in place, and MUST create no Admin Wallet debit.

#### Scenario: Pending withdraw does not debit Admin Wallet
- **WHEN** a verified customer successfully submits a pending withdraw of `100.00`
- **THEN** the customer recharge balance decreases by `100.00` and no Admin Wallet `customer_withdraw` debit is created yet

#### Scenario: Approved withdraw finalizes custody debit
- **WHEN** a verified admin approves a pending withdraw of `100.00` and Admin Wallet float is sufficient
- **THEN** the withdraw becomes `completed`, the Admin Wallet balance decreases by `100.00`, and exactly one completed `customer_withdraw` debit exists for that customer wallet transaction

#### Scenario: Approve does not mutate customer_funding credits
- **WHEN** a verified admin approves a customer withdraw
- **THEN** no historical Admin Wallet `customer_funding` credit row is deleted or amount-reduced for that withdraw

#### Scenario: Admin Wallet float shortfall rejects approve
- **WHEN** an admin attempts to approve a pending withdraw that exceeds Admin Wallet balance
- **THEN** the system responds `409 Conflict`, the withdraw remains `pending`, the customer reserved balance stays reduced, and no Admin Wallet debit is created
