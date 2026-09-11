## ADDED Requirements

### Requirement: Withdraw client documentation covers meal-stop maximum
The system SHALL provide frontend documentation that explains the withdrawable formula `max(0, recharge_balance - meal_stop_threshold)`, how to read `withdrawable_balance` / `meal_stop_threshold` from the wallet API, input validation UX, and backend error handling for over-limit amounts. Documentation MUST cover mobile and customer web wallets at:

- `wallet/docs/frontend/manual-wallet-funding.md` (update), and/or dedicated withdraw sections as needed
- Clear copy examples such as keeping ৳`meal_stop_threshold` for meal service when the user exceeds maximum withdrawable

#### Scenario: Mobile engineer can implement withdraw screen limits
- **WHEN** a mobile engineer reads the wallet frontend funding/withdraw documentation
- **THEN** the doc states the maximum withdrawable formula, which wallet fields to display, and how to block amounts above the maximum before submit

#### Scenario: Customer web engineer gets the same rule
- **WHEN** a customer-web engineer reads the same documentation set
- **THEN** the doc applies the identical recharge − meal_stop rule and states that backend validation is authoritative

### Requirement: Admin withdraw approve documentation shows remaining balance
The system SHALL document admin funding approve UI expectations: show customer balance before, withdraw amount, projected remaining recharge/total as applicable, and `meal_stop_threshold`, and clarify that Admin Wallet custody decreases via `customer_withdraw` on approve (platform balance down; lifetime `total_customer_funding` unchanged; use net custody for “funding left”).

#### Scenario: Admin panel engineer sees approve summary fields
- **WHEN** an admin-panel engineer opens the updated wallet/admin funding docs
- **THEN** the doc lists approve-screen fields for before/amount/remaining and warns not to expect `total_customer_funding` to decrease on approve
