## ADDED Requirements

### Requirement: Wallet transactions expose delivery-fee context for fee charges

For wallet transactions created as delivery-fee payments (`type=delivery_fee_payment`), the customer wallet transaction list and detail responses MUST expose structured delivery-fee fields so clients can render history without undocumented parsing. Exposed fields MUST include at least: billing month, billing year (or a combined period label), charged amount, and a processed-by-admin signal or actor display identity when available. Meal-delivery payment fields MUST remain absent/null for these rows. Non-delivery-fee transactions MUST omit delivery-fee fields or return them as null/absent without breaking existing clients.

#### Scenario: List includes delivery-fee fields after deduct

- **WHEN** a verified customer lists wallet transactions after a successful September 2026 delivery-fee debit of `300.00`
- **THEN** that transaction includes delivery-fee billing period September 2026 and amount `300.00`, and does not present meal period/service date as required meal-payment fields

#### Scenario: Meal payment row has no delivery-fee block

- **WHEN** a verified customer lists wallet transactions that include a meal-delivery payment
- **THEN** the meal payment item does not require delivery-fee billing month/year fields (null/absent)

### Requirement: Delivery-fee debits are distinguishable from meal payments in customer history

Customer-facing wallet history MUST allow clients to distinguish `delivery_fee_payment` debits from meal-delivery `payment` debits using the transaction `type` and/or dedicated delivery-fee context block. Clients MUST be able to label delivery-fee rows as delivery fee deductions without treating them as meal charges.

#### Scenario: Types differ in history payload

- **WHEN** a customer has both a meal-delivery payment and a delivery-fee payment in history
- **THEN** the two transactions expose different types and/or context blocks so the client can render them separately
