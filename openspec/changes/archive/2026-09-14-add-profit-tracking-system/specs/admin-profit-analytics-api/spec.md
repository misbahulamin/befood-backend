## ADDED Requirements

### Requirement: Only verified admins can access Admin Profit APIs
The system SHALL expose Admin Profit endpoints under the web admin API prefix (`/api/v1/web/admin-profit/`) and MUST require an authenticated verified admin. Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403` (or `404` when concealing existence is required by project policy). Customers MUST NOT access profit ledger or analytics data.

#### Scenario: Verified admin can read profit dashboard
- **WHEN** an authenticated verified admin requests the Admin Profit dashboard
- **THEN** the system responds `200` with profit aggregate fields

#### Scenario: Customer cannot access Admin Profit
- **WHEN** an authenticated customer requests an Admin Profit endpoint
- **THEN** the system denies access and does not return profit data

### Requirement: Profit dashboard reads saved ledger aggregates only
The system SHALL provide `GET /api/v1/web/admin-profit/dashboard/` that returns at least: `lifetime_profit`, `month_profit`, `today_profit`, package-wise profit breakdown, meal-period profit breakdown, and a daily profit series suitable for charts. Aggregates MUST be computed from persisted profit ledger rows only. The dashboard MUST NOT rescan all deliveries to recompute profit from live slot joins on each request.

#### Scenario: Dashboard returns lifetime month and today totals
- **WHEN** a verified admin requests the profit dashboard after charged deliveries with profit rows exist across prior days and today
- **THEN** the response includes `lifetime_profit`, `month_profit`, and `today_profit` as decimal money strings derived from the ledger

#### Scenario: Dashboard includes package and meal-period breakdowns
- **WHEN** charged profit rows exist for more than one package and both lunch and dinner
- **THEN** the response includes package-wise rows (deliveries, revenue, food cost, profit) and a lunch vs dinner profit breakdown

#### Scenario: Dashboard includes daily profit chart data
- **WHEN** profit rows exist on multiple service dates in the default chart window (current calendar month unless documented otherwise)
- **THEN** the response includes a daily series of `{date, profit}` (and MAY include revenue/cost) ordered by date ascending

### Requirement: Profit history supports allowlisted filters and pagination
The system SHALL provide `GET /api/v1/web/admin-profit/history/` as a paginated list of profit ledger rows ordered newest-first (by service date then created/id tie-breaker, or documented equivalent deterministic order). The list MUST support allowlisted filters: `start_date`, `end_date`, package identifier, customer identifier, and `meal_period`. Unsupported filters MUST be rejected with `400`. Date-range filters MUST use `service_date` unless a documented alternate axis is explicitly provided.

#### Scenario: Filter by date range and package
- **WHEN** a verified admin requests history with `start_date`, `end_date`, and a package public id
- **THEN** only matching profit rows in that service-date range for that package are returned

#### Scenario: Filter by customer and meal period
- **WHEN** a verified admin requests history filtered to one customer and `meal_period=lunch`
- **THEN** only that customer’s lunch profit rows are returned

#### Scenario: Unsupported filter is rejected
- **WHEN** a verified admin supplies an unsupported filter field
- **THEN** the system responds `400 Bad Request`

### Requirement: Custom date range and yearly profit are queryable
The system MUST allow admins to obtain profit totals for an arbitrary inclusive `service_date` range (including a full calendar year) via dashboard query parameters and/or history/aggregate queries documented in OpenAPI. Yearly and custom-range totals MUST equal the sum of matching ledger `profit_amount` values.

#### Scenario: Custom range profit matches ledger sum
- **WHEN** a verified admin requests profit for `2026-09-01` through `2026-09-13`
- **THEN** the returned profit equals the sum of ledger profit amounts with `service_date` in that inclusive range

### Requirement: Customer-wise profit is queryable
The system SHALL support customer-scoped profit analytics: for a given customer (and optional date range), totals MUST include meal/delivery count, revenue, food cost, and profit from the ledger. This MAY be exposed via history filters plus documented aggregate fields, or a dedicated verified-admin aggregate response section/endpoint documented in OpenAPI.

#### Scenario: Customer September profit
- **WHEN** a verified admin requests profit analytics for Customer A limited to September 2026
- **THEN** the response totals reflect only that customer’s September ledger rows

### Requirement: Admin Profit OpenAPI and frontend docs exist
The system SHALL document Admin Profit dashboard and history contracts in OpenAPI and provide frontend documentation under `admin_wallet/docs/frontend/` (or app-local equivalent) covering auth, endpoints, field meanings, chart series shape, filter parameters, and migration notes away from wallet-dashboard profit fields.

#### Scenario: Frontend doc explains profit dashboard vs wallet dashboard
- **WHEN** a frontend engineer opens the Admin Profit frontend doc
- **THEN** the doc states wallet dashboard no longer returns profit fields and shows how to call Admin Profit APIs for cards and graphs
