## ADDED Requirements

### Requirement: Customer withdraw does not reduce lifetime customer_funding counter
When a customer withdraw completes and Admin Wallet custody is debited, the system MUST record the outflow as type `customer_withdraw` and MUST increment `total_customer_withdrawals`. The system MUST NOT decrease `total_customer_funding` for that withdraw. Platform Admin Wallet `balance` MUST decrease by the withdraw amount when float is sufficient.

#### Scenario: Lifetime funding counter stays after withdraw
- **WHEN** Admin Wallet has `total_customer_funding` `500.00` and a customer withdraw of `100.00` is approved with sufficient float
- **THEN** `total_customer_funding` remains `500.00`, `total_customer_withdrawals` increases by `100.00`, and Admin Wallet `balance` decreases by `100.00`

### Requirement: Net customer funding custody is exposed to admins
The Admin Wallet summary and/or dashboard MUST expose a derived net customer funding custody amount equal to `total_customer_funding - total_customer_withdrawals` (non-negative presentation as documented) so operators can see remaining customer custody liability without treating `total_customer_funding` as a mutable running balance.

#### Scenario: Dashboard shows net after withdraw
- **WHEN** `total_customer_funding` is `500.00` and `total_customer_withdrawals` is `100.00` and a verified admin loads Admin Wallet summary or dashboard
- **THEN** the response includes net customer funding custody of `400.00` (field name documented, e.g. `net_customer_funding`)

## MODIFIED Requirements

### Requirement: Successful customer withdraw debits Admin Wallet custody
When a customer wallet withdraw is approved and completes successfully, the system SHALL debit the Admin Wallet by the same amount as a completed `customer_withdraw` transaction (direction `debit`), linked to the customer wallet transaction, inside the same database transaction as completing the customer withdraw. Pending withdraw submission MUST NOT debit Admin Wallet. If the Admin Wallet balance is insufficient for that debit at approve time, the system MUST reject the approve without completing the customer withdraw and without creating an Admin Wallet debit. The withdraw custody path MUST NOT post a debit typed as `customer_funding` and MUST NOT rewrite historical `customer_funding` credits.

#### Scenario: Customer withdraw decreases Admin Wallet balance
- **WHEN** a verified admin approves a customer withdraw of `100.00` and the Admin Wallet balance is at least `100.00`
- **THEN** the Admin Wallet balance decreases by `100.00` and exactly one completed `customer_withdraw` debit of `100.00` exists for that customer wallet transaction

#### Scenario: Insufficient Admin Wallet float blocks customer withdraw approve
- **WHEN** an admin attempts to approve a withdraw of `100.00` but the Admin Wallet balance is less than `100.00`
- **THEN** the system rejects the approve, the customer withdraw remains pending with reservation intact, and no Admin Wallet debit is created

#### Scenario: Withdraw custody uses customer_withdraw type
- **WHEN** a customer withdraw is approved successfully
- **THEN** the Admin Wallet ledger row for that event has type `customer_withdraw` and not type `customer_funding`
