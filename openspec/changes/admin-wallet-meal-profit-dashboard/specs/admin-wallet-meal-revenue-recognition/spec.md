## ADDED Requirements

### Requirement: Meal profit is reportable separately from meal revenue
The system SHALL expose realized meal **profit** for admin reporting as a metric distinct from recognized meal **revenue** (`charged_amount` sums) and distinct from Admin Wallet cash credits. Profit MUST be based on published slot `profit_snapshot` associated with charged meal deliveries. Meal revenue metrics MUST continue to reflect charged delivery amounts without requiring an Admin Wallet cash credit at meal time. Clients MUST be able to display both metrics without treating funding custody credits as either meal revenue or meal profit.

#### Scenario: Dashboard can show revenue and profit for the same charged meal
- **WHEN** a charged delivery has `charged_amount` `59.10` and published slot `profit_snapshot` `3.10`
- **THEN** meal-revenue reporting includes `59.10` and meal-profit reporting includes `3.10` while Admin Wallet cash balance is unchanged by the meal charge itself

#### Scenario: Funding is neither meal revenue nor meal profit
- **WHEN** only a `customer_funding` recharge credit exists in a period
- **THEN** meal-revenue and meal-profit period metrics do not treat that funding amount as a meal delivery payment or meal profit
