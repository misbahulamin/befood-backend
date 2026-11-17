# Spec Delta

## MODIFIED Requirements

### Requirement: Meal revenue remains reportable for admins
The system SHALL expose recognized meal business revenue for admin reporting (dashboard and/or summary fields) based on (1) successful customer regular meal-delivery charges and (2) realized delivered Guest Meal prepaid amounts, without relying on a second Admin Wallet cash credit. Lifetime/period meal-revenue figures MUST be distinguishable from `customer_funding` custody credits. Scheduled Guest Meal prepaid amounts MUST NOT count as delivered/recognized meal revenue until delivery realization.

#### Scenario: Dashboard meal revenue reflects charged deliveries
- **WHEN** one or more meal-delivery wallet charges completed successfully in the current period
- **THEN** admin dashboard/summary meal-revenue (customer payment) metrics include those charged amounts even though Admin Wallet cash was not re-credited at meal time

#### Scenario: Funding credit is not labeled as meal revenue
- **WHEN** the only Admin Wallet credit in a period is a `customer_funding` recharge credit
- **THEN** meal-revenue metrics do not treat that funding credit as a meal-delivery customer payment

#### Scenario: Delivered guest prepaid amount becomes recognized revenue
- **WHEN** a prepaid Guest Meal order with `total_amount` `140.00` is delivered and realized in the period
- **THEN** recognized meal-revenue metrics for that period include `140.00` exactly once and Admin Wallet cash is not increased by a guest meal credit

#### Scenario: Scheduled guest prepaid amount is not recognized revenue
- **WHEN** a Guest Meal order is prepaid but still scheduled
- **THEN** recognized delivered meal-revenue metrics do not include that prepaid amount

### Requirement: Meal profit is reportable separately from meal revenue
The system SHALL expose realized meal **profit** for admin reporting as a metric distinct from recognized meal **revenue** and distinct from Admin Wallet cash credits. Regular meal profit MUST continue to use published slot `profit_snapshot` associated with charged meal deliveries. Guest Meal profit MUST use realized guest revenue minus attributable published-slot costs for delivered guest quantities. Meal revenue metrics MUST continue to reflect charged regular delivery amounts plus realized guest amounts without requiring an Admin Wallet cash credit at meal time. Clients MUST be able to display both metrics without treating funding custody credits as either meal revenue or meal profit.

#### Scenario: Dashboard can show revenue and profit for the same charged meal
- **WHEN** a charged delivery has `charged_amount` `59.10` and published slot `profit_snapshot` `3.10`
- **THEN** meal-revenue reporting includes `59.10` and meal-profit reporting includes `3.10` while Admin Wallet cash balance is unchanged by the meal charge itself

#### Scenario: Funding is neither meal revenue nor meal profit
- **WHEN** only a `customer_funding` recharge credit exists in a period
- **THEN** meal-revenue and meal-profit period metrics do not treat that funding amount as a meal delivery payment or meal profit

#### Scenario: Delivered guest contributes revenue and profit separately
- **WHEN** a delivered Guest Meal recognizes revenue `140.00` and attributable costs `61.00`
- **THEN** meal-revenue reporting includes `140.00` and meal-profit reporting includes `79.00` without an Admin Wallet cash credit for the guest amount

## ADDED Requirements

### Requirement: Guest prepaid collection is not Admin Wallet meal credit
Guest Meal wallet debit at purchase MUST NOT create an Admin Wallet meal-delivery cash credit, and delivery-time Guest Meal realization MUST NOT create one either. Prepaid guest collection remains a customer-wallet movement; realization is reporting-only against the meal profit/revenue ledgers.

#### Scenario: Guest purchase does not cash-credit Admin Wallet as meal revenue
- **WHEN** a customer successfully purchases a Guest Meal and the customer wallet is debited
- **THEN** Admin Wallet cash balance is not increased by that guest debit as a meal-delivery credit
