## Purpose

Recognize meal-delivery revenue for admin reporting without cash-crediting the Admin Wallet a second time after customer funding custody.
## Requirements
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

### Requirement: Meal profit is reportable separately from meal revenue
The system SHALL expose realized meal **profit** for admin reporting as a metric distinct from recognized meal **revenue** (`charged_amount` sums) and distinct from Admin Wallet cash credits. Profit MUST be based on published slot `profit_snapshot` associated with charged meal deliveries. Meal revenue metrics MUST continue to reflect charged delivery amounts without requiring an Admin Wallet cash credit at meal time. Clients MUST be able to display both metrics without treating funding custody credits as either meal revenue or meal profit.

#### Scenario: Dashboard can show revenue and profit for the same charged meal
- **WHEN** a charged delivery has `charged_amount` `59.10` and published slot `profit_snapshot` `3.10`
- **THEN** meal-revenue reporting includes `59.10` and meal-profit reporting includes `3.10` while Admin Wallet cash balance is unchanged by the meal charge itself

#### Scenario: Funding is neither meal revenue nor meal profit
- **WHEN** only a `customer_funding` recharge credit exists in a period
- **THEN** meal-revenue and meal-profit period metrics do not treat that funding amount as a meal delivery payment or meal profit

