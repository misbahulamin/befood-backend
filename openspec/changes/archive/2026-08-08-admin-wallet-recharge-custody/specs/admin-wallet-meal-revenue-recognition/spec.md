## ADDED Requirements

### Requirement: Meal-delivery charge does not cash-credit Admin Wallet
When a customer meal-delivery wallet charge completes successfully, the system MUST NOT increase the Admin Wallet cash balance for that charge. Prepaid funds were already reflected via customer funding custody when the customer recharged (or via other Admin Wallet credits).

#### Scenario: Delivered meal leaves Admin Wallet cash balance unchanged by meal credit
- **WHEN** an authorized operator marks a delivery `delivered` and the customer wallet is successfully debited `62.00`
- **THEN** the system does not create a new Admin Wallet cash credit that increases balance by `62.00` for that delivery payment

#### Scenario: Recharge then meal does not double-count cash
- **WHEN** a customer recharges `500.00` (Admin Wallet credited `500.00`) and later a meal charge of `62.00` succeeds
- **THEN** the Admin Wallet cash balance increases by `500.00` from funding only, not by an additional `62.00` from the meal charge

### Requirement: Meal revenue remains reportable for admins
The system SHALL expose recognized meal-delivery revenue for admin reporting (dashboard and/or summary fields) based on successful customer meal charges, without relying on a second Admin Wallet cash credit. Lifetime/period meal-revenue figures MUST be distinguishable from `customer_funding` custody credits.

#### Scenario: Dashboard meal revenue reflects charged deliveries
- **WHEN** one or more meal-delivery wallet charges completed successfully in the current period
- **THEN** admin dashboard/summary meal-revenue (customer payment) metrics include those charged amounts even though Admin Wallet cash was not re-credited at meal time

#### Scenario: Funding credit is not labeled as meal revenue
- **WHEN** the only Admin Wallet credit in a period is a `customer_funding` recharge credit
- **THEN** meal-revenue metrics do not treat that funding credit as a meal-delivery customer payment
