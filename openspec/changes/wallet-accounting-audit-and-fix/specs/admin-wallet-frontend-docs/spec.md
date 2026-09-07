## ADDED Requirements

### Requirement: Docs explain expense vs customer withdrawal and provider ref reuse
The Admin Wallet and wallet funding documentation MUST state that: (1) dashboard `today_expense` / `month_expense` mean business `EXPENSE_TYPES` only and do not include customer withdraw custody debits; (2) period customer-withdrawal fields (or equivalent documented names) show approved customer payouts; (3) approve withdraw posts Admin Wallet `customer_withdraw` and reduces balance without counting as expense; (4) after a rejected provider recharge (`failed`), the same `transaction_id` may be reused, while pending or completed refs remain blocked. Frontend docs MUST call out the semantic change for expense cards so Admin Panel engineers update labels/mappings.

#### Scenario: Frontend doc distinguishes expense and customer withdrawal
- **WHEN** a frontend engineer opens the Admin Wallet frontend documentation
- **THEN** the doc maps expense cards to expense-typed debits and describes separate customer-withdrawal period totals

#### Scenario: Funding docs describe transaction id reuse after reject
- **WHEN** a frontend or backend engineer reads wallet funding documentation for provider recharge
- **THEN** the doc states that rejected/failed provider transaction ids may be reused and pending/completed ones may not
