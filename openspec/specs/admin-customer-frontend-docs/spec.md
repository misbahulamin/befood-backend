## Purpose

Frontend developer documentation for Admin Panel Customer list and details integration with admin customer web APIs.

## Requirements

### Requirement: Frontend documentation for Admin Customer Management

The system SHALL include frontend developer documentation at `user_management/docs/frontend/admin-customer-management.md` (kebab-case path) that describes how the Admin Panel Customer section integrates with the admin customer web APIs. The documentation MUST be written for a reader who does not already know the feature, and MUST cover page structure, API usage order, auth headers, and UI states.

#### Scenario: Doc file present after implementation

- **WHEN** this change is implemented
- **THEN** `user_management/docs/frontend/admin-customer-management.md` exists and describes the Customer List and Customer Details flows

### Requirement: Document Customer List page contract

The frontend documentation MUST specify the Customer List page structure and UI fields: profile image (with null/placeholder handling), name, email, phone, account/verification status, and active package. It MUST document search (name/email/phone), filters (active/inactive, has active order / no active order, package-wise, registration date range), pagination, and the primary action to open Customer Details. It MUST include example list request/response shapes and loading, empty, and error state guidance consistent with the existing Admin Panel.

#### Scenario: List UI mapping is documented

- **WHEN** a frontend developer follows the Customer List section of the doc
- **THEN** they can map each table column and filter control to a specific API field or query parameter

### Requirement: Document Customer Details tabs

The frontend documentation MUST specify a Customer Details page with tabs:

1. Overview — basic information and summary metrics
2. Active Order — current package details
3. Order History — previous orders
4. Meal History — delivered / off / other delivery statuses
5. Wallet History — transactions
6. Activity History — composed customer actions

For each tab, the doc MUST state which endpoint to call, key response fields to render, pagination behavior for historical tabs, and empty-state copy guidance.

#### Scenario: Tab-to-endpoint mapping documented

- **WHEN** a frontend developer implements the Details tabs
- **THEN** each tab has a documented API path and example success payload fields sufficient to build the UI without reading backend source

### Requirement: Document auth, client, and UX consistency

The frontend documentation MUST state that these APIs are Admin web-only, require verified-admin authentication, and should use the project's Admin Panel patterns for tables, cards, pagination, and loading/empty/error handling. It MUST note that customer verification status binds to email verification (`is_email_verified` / documented verification field), not admin `is_verified`.

#### Scenario: Auth and verification semantics documented

- **WHEN** a frontend developer reads the auth section
- **THEN** they know which token/permission is required and how to display verification vs account active status
