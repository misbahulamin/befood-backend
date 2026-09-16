## ADDED Requirements

### Requirement: Dashboard includes meal profit summary and package breakdown
The system SHALL extend the Admin Wallet dashboard representation with additive fields `total_profit`, `month_profit`, and `profit_by_package` (with `lifetime` and `month` package rows) in addition to existing cash and meal-revenue summary cards. Existing dashboard fields (`today_income`, `month_revenue`, funding/withdrawal totals, `recent_transactions`, etc.) MUST remain available and MUST retain their current meanings. Access control for the dashboard MUST remain verified-admin only.

#### Scenario: Dashboard returns profit fields with existing cards
- **WHEN** a verified admin requests the Admin Wallet dashboard after charged meal deliveries and cash credits exist
- **THEN** the response includes the existing balance/today/month cash fields and also `total_profit`, `month_profit`, and `profit_by_package`

#### Scenario: Non-admin still denied after profit fields added
- **WHEN** an authenticated customer requests the Admin Wallet dashboard
- **THEN** the system denies access and does not return profit or wallet data
