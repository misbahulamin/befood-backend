## ADDED Requirements

### Requirement: Payment type is used for meal-delivery wallet charges

The system SHALL record successful meal-delivery wallet charges as ledger transactions with `type=payment` and `direction=debit`, distinct from customer-initiated `withdraw` funding debits and from `recharge` credits. Order create and wallet minimum-balance eligibility checks MUST continue to avoid creating payment debits. Manual recharge and withdraw funding rules from this capability remain unchanged.

#### Scenario: Delivered meal creates payment debit not withdraw

- **WHEN** a delivery is successfully marked `delivered` and the wallet is charged
- **THEN** the ledger row has `type=payment` and `direction=debit`, not `type=withdraw`

#### Scenario: Order create still does not create payment debit

- **WHEN** a verified customer creates a meal package order with sufficient minimum wallet balance
- **THEN** the system does not create a `type=payment` debit solely due to order creation
