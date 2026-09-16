## ADDED Requirements

### Requirement: Admin Wallet dashboard excludes meal profit fields
The system SHALL keep the Admin Wallet dashboard focused on cash/custody metrics (balance, today/month income and expense, customer funding/withdrawals, meal revenue recognition totals as already defined, recent wallet transactions). The Admin Wallet dashboard MUST NOT return `total_profit`, `month_profit`, or `profit_by_package`, and MUST NOT scan deliveries to compute realized meal margin on that endpoint. Meal profit analytics MUST be served only by Admin Profit APIs.

#### Scenario: Wallet dashboard omits profit fields
- **WHEN** a verified admin requests `GET /api/v1/web/admin-wallet/dashboard/`
- **THEN** the response includes cash/custody summary fields and does not include `total_profit`, `month_profit`, or `profit_by_package`

#### Scenario: Wallet dashboard still returns cash cards
- **WHEN** a verified admin requests the Admin Wallet dashboard after credits and expenses exist
- **THEN** the response still includes balance, today/month cash aggregates, and recent transactions

## REMOVED Requirements

### Requirement: Dashboard includes meal profit summary and package breakdown
**Reason:** Realized meal profit moves to a dedicated immutable profit ledger and Admin Profit APIs; recomputing profit on the wallet dashboard does not scale and conflates cash custody with margin analytics.
**Migration:** Use `GET /api/v1/web/admin-profit/dashboard/` (and history) instead of wallet dashboard profit fields. Update Admin Panel profit cards to the new endpoints; treat removal of `total_profit`, `month_profit`, and `profit_by_package` from the wallet dashboard as a breaking contract change.
