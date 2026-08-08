## ADDED Requirements

### Requirement: Successful recharge syncs Admin Wallet custody
When a customer manual recharge completes successfully, the system MUST also credit the platform Admin Wallet custody ledger for the same amount (idempotent per customer wallet transaction), subject to the Admin Wallet funding-custody feature flag when present. Customer-facing recharge response fields remain the wallet balance and transaction identity; Admin Wallet details are not required in the customer response.

#### Scenario: Recharge credits customer wallet and Admin Wallet together
- **WHEN** a verified customer successfully recharges `500.00`
- **THEN** the customer wallet balance increases by `500.00` and the Admin Wallet receives a matching custody credit for that recharge transaction

#### Scenario: Idempotent recharge does not double-credit either ledger
- **WHEN** the same recharge idempotency key and amount are replayed after success
- **THEN** neither the customer wallet nor the Admin Wallet applies a second credit for that event

### Requirement: Successful withdraw syncs Admin Wallet custody
When a customer manual withdraw completes successfully, the system MUST also debit the platform Admin Wallet custody ledger for the same amount (idempotent per customer wallet transaction). If Admin Wallet custody cannot cover the debit, the system MUST reject the withdraw without changing the customer wallet balance.

#### Scenario: Withdraw debits customer wallet and Admin Wallet together
- **WHEN** a verified customer successfully withdraws `100.00` and Admin Wallet float is sufficient
- **THEN** the customer wallet balance decreases by `100.00` and the Admin Wallet receives a matching custody debit for that withdraw transaction

#### Scenario: Admin Wallet float shortfall rejects withdraw
- **WHEN** a customer requests a withdraw that exceeds Admin Wallet balance
- **THEN** the system rejects the withdraw and the customer wallet balance is unchanged
