## ADDED Requirements

### Requirement: Dashboard exposes lifetime and month realized meal profit
The system SHALL include decimal money fields `total_profit` and `month_profit` on the Admin Wallet dashboard response. `total_profit` MUST equal the sum of published menu slot `profit_snapshot` values for all meal deliveries with `payment_status=charged` and a non-null `charged_amount` (lifetime). `month_profit` MUST use the same recognition rule restricted to deliveries whose charge recognition timestamp (`updated_at`) falls within the current calendar month bounds used by existing Admin Wallet period helpers. Profit MUST NOT be derived from Admin Wallet cash credits such as `customer_funding`. Money values MUST be quantized to project money precision and returned as decimal strings consistent with other dashboard amounts.

#### Scenario: Charged deliveries contribute slot profit to totals
- **WHEN** two charged deliveries resolve to published slots with `profit_snapshot` of `3.10` and `4.00`
- **THEN** `total_profit` equals `7.10` (subject to quantization) and those amounts are included in `month_profit` when both charges fall in the current month window

#### Scenario: Funding credit does not increase meal profit
- **WHEN** the only Admin Wallet activity in the period is a completed `customer_funding` credit and no charged meal deliveries exist in that period
- **THEN** `month_profit` remains `0.00` and `month_revenue` may still reflect the funding credit

#### Scenario: Missing profit snapshot contributes zero profit
- **WHEN** a charged delivery cannot resolve a published slot `profit_snapshot`
- **THEN** the delivery contributes `0.00` to profit totals and the dashboard still responds `200`

### Requirement: Dashboard exposes package-wise profit breakdown for lifetime and month
The system SHALL include a `profit_by_package` object on the Admin Wallet dashboard with `lifetime` and `month` arrays. Each row MUST identify the meal package (`package_public_id`, `package_name`) and MUST include at least `charged_deliveries`, `revenue` (sum of `charged_amount`), and `profit` (sum of resolved `profit_snapshot`, treating unresolved as zero). Rows MUST be ordered by descending `profit`, then `package_name`. Packages with no charged deliveries in the scope MUST be omitted. The `month` array MUST apply the same month window as `month_profit`. The `lifetime` array MUST apply the same lifetime scope as `total_profit`. Sum of row `profit` values in each array MUST equal the corresponding top-level profit field.

#### Scenario: Click-ready month breakdown matches month_profit
- **WHEN** charged deliveries exist for packages A and B in the current month with profits `10.00` and `5.00`
- **THEN** `profit_by_package.month` contains two rows totaling `15.00` profit matching `month_profit`, with package A listed before package B when profits differ

#### Scenario: Lifetime breakdown groups by package
- **WHEN** multiple charged deliveries for the same meal package exist across months
- **THEN** `profit_by_package.lifetime` contains a single row for that package with aggregated `charged_deliveries`, `revenue`, and `profit`

### Requirement: Profit aggregation reuses published slot and package resolution rules
The system MUST resolve each delivery’s meal package via the same order/subscription meal association used elsewhere for delivery meal identity, and MUST resolve the published slot via the same `(meal, service_date, meal_period)` rules used for delivery wallet charging. The system MUST NOT recompute profit from live ingredient catalog prices when a published `profit_snapshot` exists.

#### Scenario: Published snapshot wins over later catalog price change
- **WHEN** a slot was published with `profit_snapshot` `3.10` and ingredient catalog costs later increase
- **THEN** profit reporting for charged deliveries of that slot still uses `3.10`
