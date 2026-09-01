## MODIFIED Requirements

### Requirement: Admin can view customer active order

The system SHALL provide a verified-admin endpoint `GET /api/v1/web/customers/{public_id}/active-subscription/` to retrieve the customer's current active **subscription** (if any), including customer display name reference, package/plan name, subscription start date, subscription end date (nullable), remaining scheduled meal count, delivered and skipped counts, and current subscription `status` as returned by the backend model/serializer (MUST NOT assume a fixed frontend enum; future values such as `pending`, `expired`, `paused`, or `completed` MUST be tolerated). When no active subscription exists, the system MUST return `200` with `active_subscription: null`. The legacy endpoint `GET .../active-order/` MAY remain as a deprecated alias for legacy active `Order` rows only and MUST include a `Deprecation` response header pointing to the subscription endpoint. Callers without verified-admin permission MUST be rejected with `401`/`403`.

#### Scenario: Customer with active subscription

- **WHEN** a verified admin requests active subscription for a customer who has `CustomerSubscription.status=active`
- **THEN** the response includes package name, start date, remaining meal count, and status from the backend serializer

#### Scenario: Customer without active subscription

- **WHEN** a verified admin requests active subscription for a customer with no active subscription
- **THEN** the system responds with `active_subscription: null` and MUST NOT return another customer's subscription

#### Scenario: Customer cannot read another customer's active subscription

- **WHEN** an authenticated customer user (Customer A) requests `GET /api/v1/web/customers/{customer-B-public-id}/active-subscription/`
- **THEN** the system responds `403 Forbidden`

### Requirement: Admin can list customer order history

The system SHALL provide a paginated verified-admin endpoint `GET /api/v1/web/customers/{public_id}/subscriptions/` listing **CustomerSubscription** records for a single customer identified by `public_id`. Each item MUST include at least subscription `public_id`, package/plan name, subscription `status` (backend model/serializer value), start date, end date (nullable), amount paid or documented billing summary when available, payment method when available, created date, delivered meal count, and skipped meal count. Results MUST be scoped to that customer only. Unknown customer `public_id` MUST return `404`. The legacy endpoint `GET .../orders/` MAY remain as a deprecated alias listing legacy `Order` rows for pre-migration history and MUST include a `Deprecation` response header.

#### Scenario: Subscription history for customer

- **WHEN** a verified admin requests subscription history for a customer who has subscribed
- **THEN** the system returns a paginated list of that customer's subscriptions with package, dates, status, and documented payment fields

#### Scenario: Subscription history does not leak other customers

- **WHEN** a verified admin requests subscription history for customer A
- **THEN** subscriptions belonging to customer B MUST NOT appear

#### Scenario: Customer cannot read another customer's subscription history

- **WHEN** an authenticated customer user (Customer A) requests `GET /api/v1/web/customers/{customer-B-public-id}/subscriptions/`
- **THEN** the system responds `403 Forbidden`

### Requirement: Admin can list customer meal history

The system SHALL provide a paginated verified-admin endpoint listing meal delivery slots (`OrderDelivery`) for a customer across **both** legacy orders and active/cancelled subscriptions. Items MUST include service date, meal period (lunch/dinner), delivery status (`scheduled|delivered|skipped|missed`), related subscription or legacy order/package references, and payment status when present. Allowlisted filters for status, meal period, and date range MAY be supported; invalid filters MUST return `400` when validation is enabled.

#### Scenario: Meal history includes subscription deliveries

- **WHEN** a verified admin requests meal history for a subscribed customer whose deliveries are linked to `CustomerSubscription`
- **THEN** those delivery slots MUST appear in the meal history

#### Scenario: Meal history includes delivered and skipped

- **WHEN** a verified admin requests meal history for a customer who has delivered and meal-off (skipped) slots
- **THEN** both delivered and skipped slots MUST be available in the history (subject to filters)

#### Scenario: Filter meal history by lunch

- **WHEN** a verified admin filters meal history with `meal_period=lunch`
- **THEN** only lunch slots MUST be returned

### Requirement: Admin can list customer meal-off history

The system SHALL provide a paginated verified-admin endpoint (or a documented meal-history filter equivalent) that lists meal-off events for a customer: skipped deliveries with service date, meal period, skip source, optional note/reason, and related subscription or legacy order/package references. The system MUST expose meal-off counts on the customer overview using subscription-aware delivery queries. Non-admin callers MUST be denied.

#### Scenario: Meal-off history includes subscription skips

- **WHEN** a customer skips a subscription-linked lunch slot
- **THEN** a verified admin retrieving meal-off history sees that date, `lunch`, skip source, and note when stored

#### Scenario: Meal-off count on overview

- **WHEN** a verified admin opens customer overview after several subscription meal-offs
- **THEN** total meal-off count MUST reflect all skipped deliveries for that customer across subscriptions and legacy orders

### Requirement: Admin can list customer wallet history

The system SHALL provide a paginated verified-admin endpoint listing wallet transactions for the customer's wallet, including type (`recharge|withdraw|payment|refund|adjustment`), direction, amount, balance after, status, method when present, external reference when present, manual funding review status when applicable, note, and timestamps. If the customer has no wallet yet, the endpoint MUST return an empty page (`200`) rather than failing, unless the customer `public_id` itself is unknown (`404`). Overview MUST expose current wallet balance when a wallet exists (otherwise null as documented).

#### Scenario: Wallet recharge and payment visible

- **WHEN** a customer has completed recharge and meal payment debit transactions
- **THEN** a verified admin wallet history lists those transactions with type, amount, and balance_after

#### Scenario: Customer without wallet

- **WHEN** a verified admin requests wallet history for a valid customer with no wallet row
- **THEN** the system responds `200` with an empty transaction list

### Requirement: Admin can view composed customer activity history

The system SHALL provide a paginated verified-admin activity feed for a customer composed from **confirmed domain events only**. Allowed event types MUST include at minimum: `subscription_created`, `subscription_cancelled`, `wallet_transaction_completed`, `meal_delivered`, `meal_skipped`, and legacy order events (`order_created`, `order_status_changed`) when legacy data exists. Each activity item MUST include `event_type`, `occurred_at`, a short summary, and references to related resources when applicable. The system MUST NOT infer activity events from `OrderDelivery.updated_at` alone. The feed is NOT required to be a complete immutable audit log, but MUST NOT invent events that did not occur.

#### Scenario: Activity includes confirmed subscription and wallet events

- **WHEN** a customer subscribes to a package and later a wallet payment completes with `status=completed`
- **THEN** a verified admin activity feed includes `subscription_created` and `wallet_transaction_completed` items ordered by time as documented

#### Scenario: Activity includes confirmed meal events

- **WHEN** a delivery slot transitions to `delivered` or `skipped` with a documented lifecycle timestamp
- **THEN** a verified admin activity feed includes `meal_delivered` or `meal_skipped` respectively

#### Scenario: Activity does not infer from generic updated_at

- **WHEN** an `OrderDelivery` row is updated for a non-lifecycle reason without status transition to delivered or skipped
- **THEN** the activity feed MUST NOT emit a spurious meal lifecycle event based solely on `updated_at`

#### Scenario: Non-admin cannot read activity

- **WHEN** a non-admin user requests customer activity
- **THEN** the system responds `401` or `403` as appropriate

#### Scenario: Customer cannot read another customer's activity

- **WHEN** an authenticated customer user (Customer A) requests `GET /api/v1/web/customers/{customer-B-public-id}/activity/`
- **THEN** the system responds `403 Forbidden`

## ADDED Requirements

### Requirement: Admin can view customer wallet overview

The system SHALL provide `GET /api/v1/web/customers/{public_id}/wallet-overview/` for verified admins returning wallet summary fields: `available_balance`, `pending_recharge_amount`, `pending_withdraw_amount`, `total_recharged`, `total_withdrawn`, `total_spent`, wallet status/currency, and count of pending funding requests when applicable. Pending amounts MUST reflect pending manual funding requests from the wallet funding review flow when that capability is deployed. If the customer has no wallet, the endpoint MUST respond `200` with documented null/zero fields. Unknown customer `public_id` MUST return `404`. A compact `wallet_summary` object with the same fields MAY appear on the customer detail overview response.

#### Scenario: Wallet overview shows pending recharge for support

- **WHEN** a verified admin requests wallet overview for a customer with a pending manual recharge of 500 BDT and no completed credit yet
- **THEN** the response includes `pending_recharge_amount` reflecting 500 BDT and `available_balance` unchanged by the pending request

#### Scenario: Wallet overview for funded customer

- **WHEN** a verified admin requests wallet overview for a customer with completed recharge, withdraw, and meal payment transactions
- **THEN** the response includes `available_balance`, `total_recharged`, `total_withdrawn`, and `total_spent` matching the wallet ledger

#### Scenario: Wallet overview without wallet row

- **WHEN** a verified admin requests wallet overview for a valid customer with no wallet
- **THEN** the system responds `200` with documented empty wallet summary fields

#### Scenario: Customer cannot read another customer's wallet overview

- **WHEN** an authenticated customer user (Customer A) requests `GET /api/v1/web/customers/{customer-B-public-id}/wallet-overview/`
- **THEN** the system responds `403 Forbidden`

## REMOVED Requirements

### Requirement: Admin can view customer active order

**Reason**: Active service is represented by `CustomerSubscription`, not legacy `Order`. Replaced by active-subscription requirement.

**Migration**: Use `GET /api/v1/web/customers/{public_id}/active-subscription/`. Legacy `active-order` alias may remain temporarily for pre-migration Order rows.

### Requirement: Admin can list customer order history

**Reason**: Customer service history is subscription-based. Legacy monthly orders remain accessible via deprecated `/orders/` alias only.

**Migration**: Use `GET /api/v1/web/customers/{public_id}/subscriptions/` for primary admin customer detail history tab.
