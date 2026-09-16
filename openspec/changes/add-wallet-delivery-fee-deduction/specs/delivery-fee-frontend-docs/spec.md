## ADDED Requirements

### Requirement: Frontend docs cover admin delivery-fee deduct workflow

The system SHALL provide frontend documentation under `wallet/docs/frontend/` (kebab-case feature doc) describing how Admin Panel implements Phase 1 delivery-fee deduction: auth header expectations, customer selection context endpoint, deduct request body (`amount`, `payment_month`, `payment_year`, `reason`), `Idempotency-Key` usage, success `201` response fields, insufficient-balance handling, and duplicate-month conflict behavior.

#### Scenario: Doc explains select → amount → confirm flow

- **WHEN** a frontend engineer opens the delivery-fee frontend doc
- **THEN** the doc describes loading customer context, entering amount, confirming deduct, and handling insufficient balance

### Requirement: Frontend docs cover history and reporting widgets

The frontend documentation MUST describe customer delivery-fee history fields (month label, amount, status, paid date) and monthly/lifetime report response fields for dashboard cards (`total_collected`, `customers_paid`, `pending_customers`, lifetime totals).

#### Scenario: Doc maps report fields to dashboard cards

- **WHEN** a frontend engineer implements September collection cards
- **THEN** the doc states which report endpoint and fields supply collected amount, paid count, and pending count

### Requirement: Frontend docs state meal vs delivery-fee wallet history

The documentation MUST state that customer wallet history uses distinct transaction typing for delivery-fee debits versus meal payments, and MUST document the delivery-fee fields clients should render (billing period, amount, processed-by admin signal when present).

#### Scenario: Doc distinguishes transaction types

- **WHEN** a mobile/web engineer reads the delivery-fee frontend doc
- **THEN** the doc tells them not to render delivery-fee rows as meal payments and shows the delivery-fee history fields
