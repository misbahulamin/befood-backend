## MODIFIED Requirements

### Requirement: Document Customer List page contract

The frontend documentation MUST specify the Customer List page structure and UI fields: profile image (with null/placeholder handling), name, email, phone, account/verification status, and **active subscription package** (with legacy order fallback documented). It MUST document search (name/email/phone), filters (active/inactive, has active subscription / no active subscription, has wallet, has pending recharge, subscription expiring soon, inactive subscription, package-wise, registration date range), pagination, and the primary action to open Customer Details. It MUST include example list request/response shapes and loading, empty, and error state guidance consistent with the existing Admin Panel.

#### Scenario: List UI mapping is documented

- **WHEN** a frontend developer follows the Customer List section of the doc
- **THEN** they can map each table column and filter control to a specific API field or query parameter

### Requirement: Document Customer Details tabs

The frontend documentation MUST specify a Customer Details page with tabs:

1. Overview — basic information, profile fields, addresses, summary metrics, and header summary cards (lazy-load only this endpoint on initial open)
2. Active Subscription — current subscription/service details
3. Subscription History — previous and cancelled subscriptions (paginated, lazy-loaded)
4. Meal History — delivered / skipped / other delivery statuses (subscription-aware, paginated, lazy-loaded)
5. Meal-offs — skipped delivery history (paginated, lazy-loaded)
6. Wallet Overview — balance, pending recharge/withdraw, and aggregate totals (lazy-loaded)
7. Wallet History — paginated transactions (lazy-loaded)
8. Activity — composed customer journey timeline from confirmed events only (paginated, lazy-loaded)

For each tab, the doc MUST state which endpoint to call, key response fields to render, pagination behavior for historical tabs, empty-state copy guidance, and MUST NOT document "Active Order" or "Order History" as primary tabs. Legacy order data MUST be documented as a collapsible **"Legacy monthly orders"** section that appears **only when** the customer has pre-migration `Order` rows, loads via deprecated `/orders/` on expand, and is hidden when no legacy orders exist.

#### Scenario: Tab-to-endpoint mapping documented

- **WHEN** a frontend developer implements the Details tabs
- **THEN** each tab has a documented API path and example success payload fields sufficient to build the UI without reading backend source

#### Scenario: Overview does not embed history

- **WHEN** a frontend developer implements the Overview tab
- **THEN** they load only `GET /api/v1/web/customers/{public_id}/` for profile, summary, active subscription summary, and wallet summary, and MUST NOT expect history arrays in that response

## ADDED Requirements

### Requirement: Document subscription-first terminology and field alignment

The frontend documentation MUST state that admin customer management uses **Subscription / Service** terminology instead of Order for the customer's current and historical service record. It MUST document known response field names (`public_id`, `delivered_count`, `skipped_count`, `full_address`, allergy fields) and warn against inventing placeholder data when API fields are null. It MUST note that meal history and metrics include subscription-linked deliveries after the backend subscription-aware update. Subscription `status` MUST be rendered from API values; frontend MUST tolerate unknown status strings without hardcoded enum-only UI.

#### Scenario: Developer avoids order-centric UI labels

- **WHEN** a frontend developer reads the terminology section
- **THEN** they implement tabs labeled Active Subscription and Subscription History rather than Active Order and Order History

#### Scenario: Field mapping prevents empty columns

- **WHEN** a frontend developer maps subscription history rows
- **THEN** they use backend field names (`delivered_count`, `skipped_count`, `public_id`) so counts and keys render correctly

### Requirement: Document header summary cards and wallet support fields

The frontend documentation MUST document header summary cards sourced from the detail `summary`, `active_subscription`, and `wallet_summary` payloads, including at minimum: active subscription package, wallet balance, meals delivered, total subscriptions, customer lifetime value, last payment date, last meal date, and current package expiry. Wallet Overview MUST document `available_balance`, `pending_recharge_amount`, `pending_withdraw_amount`, `total_recharged`, `total_withdrawn`, and `total_spent` for admin support scenarios (e.g., "recharge submitted but balance not updated").

#### Scenario: Support scenario documented

- **WHEN** a frontend developer implements Wallet Overview
- **THEN** they can display pending recharge amount separately from available balance using documented API fields

### Requirement: Document performance and lazy-loading rules

The frontend documentation MUST state that customer detail history tabs are lazy-loaded on tab activation and MUST NOT be prefetched as large nested arrays inside the overview API response. Loading skeleton, empty, and error states MUST be documented per tab.

#### Scenario: Lazy load pattern documented

- **WHEN** a frontend developer implements tab switching
- **THEN** they enable history API queries only when the corresponding tab is active, matching the documented React Query pattern

### Requirement: Document QA customer scenarios

The frontend documentation MUST include a QA matrix covering at minimum: Customer A (active subscription + wallet + delivered meals — all data visible), Customer B (cancelled subscription — history visible, active null), Customer C (no subscription, no wallet — empty states), and Customer D (legacy order only — legacy collapsible section visible, subscription primary empty).

#### Scenario: QA matrix present

- **WHEN** QA follows the documentation verification section
- **THEN** they can validate all four customer scenarios without guessing expected UI behavior
