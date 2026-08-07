## Purpose

Verified-admin web APIs for a customer's active order, order/meal/meal-off/wallet history, and composed activity feed, scoped by customer `public_id`.

## Requirements

### Requirement: Admin can view customer active order

The system SHALL provide a verified-admin endpoint to retrieve the customer's current active order (if any), including customer display name reference, package name, order start date, order end date, remaining meal count (scheduled deliveries), and current order status. When no active order exists, the system MUST return an empty representation (`200` with null/empty body fields as documented) or an explicit not-found style empty state that does not leak other customers' data—behavior MUST be documented and consistent. Callers without verified-admin permission MUST be rejected with `401`/`403`.

#### Scenario: Customer with active package

- **WHEN** a verified admin requests active order for a customer who has an order with `order_status=active`
- **THEN** the response includes package name, start/end dates, remaining meal count, and status

#### Scenario: Customer without active package

- **WHEN** a verified admin requests active order for a customer with no active order
- **THEN** the system responds with the documented empty/null active-order representation and MUST NOT return another customer's order

### Requirement: Admin can list customer order history

The system SHALL provide a paginated verified-admin endpoint listing orders for a single customer identified by `public_id`. Each item MUST include at least order `public_id`, order month (when present), package name snapshot, order dates, order status, and payment-related fields available from the order/delivery domain (as documented). Results MUST be scoped to that customer only. Unknown customer `public_id` MUST return `404`.

#### Scenario: Order history for customer

- **WHEN** a verified admin requests order history for a customer who has placed orders
- **THEN** the system returns a paginated list of that customer's orders with package, dates, and status fields

#### Scenario: Order history does not leak other customers

- **WHEN** a verified admin requests order history for customer A
- **THEN** orders belonging to customer B MUST NOT appear

### Requirement: Admin can list customer meal history

The system SHALL provide a paginated verified-admin endpoint listing meal delivery slots (`OrderDelivery`) for a customer's orders. Items MUST include service date, meal period (lunch/dinner), delivery status (`scheduled|delivered|skipped|missed`), related order/package references, and payment status when present. Allowlisted filters for status, meal period, and date range MAY be supported; invalid filters MUST return `400` when validation is enabled.

#### Scenario: Meal history includes delivered and skipped

- **WHEN** a verified admin requests meal history for a customer who has delivered and meal-off (skipped) slots
- **THEN** both delivered and skipped slots MUST be available in the history (subject to filters)

#### Scenario: Filter meal history by lunch

- **WHEN** a verified admin filters meal history with `meal_period=lunch`
- **THEN** only lunch slots MUST be returned

### Requirement: Admin can list customer meal-off history

The system SHALL provide a paginated verified-admin endpoint (or a documented meal-history filter equivalent) that lists meal-off events for a customer: skipped deliveries with service date, meal period, skip source, optional note/reason, and related order/package references. The system MUST also support exposing meal-off counts on the customer overview (see directory capability). Non-admin callers MUST be denied.

#### Scenario: Meal-off history row

- **WHEN** a customer has skipped a lunch slot with an optional note
- **THEN** a verified admin retrieving meal-off history sees that date, `lunch`, skip source, and note when stored

#### Scenario: Meal-off count on overview

- **WHEN** a verified admin opens customer overview after several meal-offs
- **THEN** total meal-off count MUST reflect the number of skipped deliveries for that customer

### Requirement: Admin can list customer wallet history

The system SHALL provide a paginated verified-admin endpoint listing wallet transactions for the customer's wallet, including type (`recharge|withdraw|payment|refund|adjustment`), direction, amount, balance after, status, method when present, note, and timestamps. If the customer has no wallet yet, the endpoint MUST return an empty page (`200`) rather than failing, unless the customer `public_id` itself is unknown (`404`). Overview MUST expose current wallet balance when a wallet exists (otherwise null/zero as documented).

#### Scenario: Wallet recharge and payment visible

- **WHEN** a customer has completed recharge and meal payment debit transactions
- **THEN** a verified admin wallet history lists those transactions with type, amount, and balance_after

#### Scenario: Customer without wallet

- **WHEN** a verified admin requests wallet history for a valid customer with no wallet row
- **THEN** the system responds `200` with an empty transaction list

### Requirement: Admin can view composed customer activity history

The system SHALL provide a paginated verified-admin activity feed for a customer composed from existing domain events (at minimum recent order lifecycle signals available in the system, meal-off skips, and wallet transactions). Each activity item MUST include `event_type`, `occurred_at`, a short summary, and references to related resources when applicable. The feed is NOT required to be a complete immutable audit log in v1, but MUST NOT invent events that did not occur.

#### Scenario: Activity includes meal-off and wallet events

- **WHEN** a customer meal-offs a slot and later a wallet payment completes
- **THEN** a verified admin activity feed includes corresponding activity items ordered by time as documented

#### Scenario: Non-admin cannot read activity

- **WHEN** a non-admin user requests customer activity
- **THEN** the system responds `401` or `403` as appropriate
