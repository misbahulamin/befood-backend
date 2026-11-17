# Spec Delta

## Purpose

Authenticated non-subscribers can check Test Meal eligibility, quote published lunch/dinner slots, and place up to two lifetime Test Meal orders with address snapshots, without creating a subscription or debiting the wallet.

## ADDED Requirements

### Requirement: Lifetime Test Meal quota of two

The system SHALL allow at most two successfully accepted Test Meal orders per authenticated customer identity for the customer's lifetime. Quota MUST count accepted orders (including later delivered or cancelled). Failed or abandoned quote/checkout attempts MUST NOT consume quota. Concurrent creates MUST NOT both succeed when remaining quota is one.

#### Scenario: First and second order accepted

- **WHEN** a non-subscriber with zero prior Test Meal orders places two valid create requests sequentially
- **THEN** both succeed and `quota_used` becomes `2`

#### Scenario: Third order rejected

- **WHEN** a customer already has two accepted Test Meal orders and requests another create
- **THEN** the system rejects with quota exhausted and creates no new order

#### Scenario: Concurrent third attempt fails safely

- **WHEN** a customer with one accepted order sends two simultaneous valid create requests
- **THEN** at most one additional order is accepted and total accepted orders never exceed two

#### Scenario: Failed checkout does not consume quota

- **WHEN** create fails validation before persistence
- **THEN** `quota_used` is unchanged

### Requirement: Active subscribers are ineligible

The system SHALL treat a customer as ineligible for Test Meal quote and create when `get_active_subscription(customer)` returns an active subscription. Active subscribers MUST be rejected even if unused quota remains. Former subscribers without an active subscription MAY order if quota remains. Existing Test Meal history MUST remain visible after the customer later subscribes.

#### Scenario: Active subscriber rejected

- **WHEN** a customer with an active subscription calls Test Meal create
- **THEN** the system rejects with reason `ACTIVE_SUBSCRIBER` and creates no order

#### Scenario: Former subscriber with remaining quota allowed

- **WHEN** a customer has no active subscription, quota remaining is at least one, and other eligibility checks pass
- **THEN** Test Meal create may proceed

#### Scenario: History retained after subscribe

- **WHEN** a customer who previously placed a Test Meal later becomes an active subscriber
- **THEN** prior Test Meal orders remain in that customer's order history

### Requirement: Eligibility API for authenticated customers

The system SHALL provide an authenticated eligibility endpoint returning `eligible`, subscriber flag, quota fields, machine reason when ineligible, and user-facing messages (Bengali required; English optional). Reasons MUST include `ACTIVE_SUBSCRIBER` and `QUOTA_EXHAUSTED`. Unauthenticated callers MUST be rejected by normal auth.

#### Scenario: Eligible customer

- **WHEN** an authenticated non-subscriber with one prior accepted Test Meal calls eligibility
- **THEN** the response has `eligible=true`, `quota_limit=2`, `quota_used=1`, `quota_remaining=1`, and `reason=null`

#### Scenario: Quota exhausted message

- **WHEN** an authenticated non-subscriber with two accepted Test Meals calls eligibility
- **THEN** `eligible=false`, `reason=QUOTA_EXHAUSTED`, and the Bengali message states that the two Test Meal quota is finished and they should subscribe

#### Scenario: Unauthenticated denied

- **WHEN** an unauthenticated client calls eligibility
- **THEN** the system returns `401` without inventing a customer identity

### Requirement: Published packages for Test Meal

The system SHALL expose customer-visible packages eligible for Test Meal ordering using existing package identity (`public_id`, name). Only active, customer-orderable published packages (`is_active` and `is_subscribable`) MUST appear. Unpublished, inactive, or unavailable packages MUST be excluded. Package names MUST NOT be hardcoded. Selected package MUST be valid for the requested service date and meal period via published menu rules.

#### Scenario: Active subscribable package listed

- **WHEN** an authenticated eligible customer requests Test Meal packages and an active subscribable package exists
- **THEN** that package appears with its public id and display name

#### Scenario: Inactive package excluded

- **WHEN** a package is inactive or not subscribable
- **THEN** it is omitted from the Test Meal packages list

#### Scenario: Package invalid for selected date rejected on quote/create

- **WHEN** the client selects a package with no published menu for the requested date and meal period
- **THEN** quote and create are rejected

### Requirement: Date, meal period, cutoff, and delivery windows

Customers MUST select `service_date`, `meal_period` (`lunch` or `dinner`), package, and optional special instructions. Business dates and cutoffs MUST use Asia/Dhaka rules and reuse existing meal-off cutoff helpers. Past dates and post-cutoff slots MUST be rejected. APIs MUST return delivery windows so clients do not hardcode them: lunch `11:00`–`14:00`, dinner `19:30`–`22:30` (local).

#### Scenario: Past date rejected

- **WHEN** create or quote uses a service date before Asia/Dhaka business today
- **THEN** the system rejects with a structured validation error

#### Scenario: Past cutoff rejected

- **WHEN** `is_past_meal_cutoff` is true for the requested date and period
- **THEN** quote and create are rejected

#### Scenario: Delivery window returned on quote

- **WHEN** a valid lunch quote is requested
- **THEN** the response includes delivery window start `11:00` and end `14:00`

### Requirement: Authoritative Test Meal quote pricing

Test Meal total MUST equal published subscription slot `final_meal_price_snapshot` for package + date + period, plus configurable box charge (default `10.00` BDT). Clients MUST NOT supply authoritative prices. Money MUST use Decimal with project precision. Quote MUST return currency, meal price, box charge, total, and delivery window. Create MUST recalculate and snapshot the authoritative price; later settings or slot price changes MUST NOT rewrite confirmed order snapshots.

#### Scenario: Slot price plus box

- **WHEN** published lunch slot price is `59.84` and box charge is `10.00`
- **THEN** quote total is `69.84` with those breakdown fields

#### Scenario: Client-supplied price ignored

- **WHEN** create includes a client total different from server calculation
- **THEN** the system uses the server total and ignores the client amount

#### Scenario: Price change after confirmation preserved

- **WHEN** an order was confirmed at total `69.84` and the slot later republishes at `80.00`
- **THEN** the confirmed order snapshots remain `69.84`

### Requirement: Address required only at confirmation

Quote MUST NOT create a finalized order. Create MUST require a customer-owned, serviceable saved delivery address (or equivalent existing address-book create/select flow), validate ownership and serviceability, and persist an immutable address snapshot on the order. Cross-customer address access MUST be denied. Test Meal MUST NOT create a monthly subscription.

#### Scenario: Quote alone creates no order

- **WHEN** a customer requests a valid quote
- **THEN** no Test Meal order row is created

#### Scenario: Own address accepted

- **WHEN** create references the customer's own serviceable address and other checks pass
- **THEN** the order is confirmed with an address snapshot

#### Scenario: Other customer's address rejected

- **WHEN** create references another customer's address public id
- **THEN** the system rejects and creates no order

#### Scenario: Unserviceable address rejected

- **WHEN** the selected address is outside serviceable delivery zones
- **THEN** create is rejected

### Requirement: Confirm with unpaid manual payment and no wallet debit

Successful create MUST set order status to confirmed (or project-equivalent ready-for-ops confirmed state), `payment_status=unpaid`, `payment_method=manual`, consume one quota unit atomically, and return order public id and confirmation details. The system MUST NOT debit wallet, call a payment gateway, or mark paid automatically. Create MUST support Idempotency-Key: same key + same payload replays the original order; same key + different payload returns conflict.

#### Scenario: Successful create

- **WHEN** an eligible customer submits a valid create with address
- **THEN** the order is confirmed, unpaid, manual, quota increments by one, and wallet balance is unchanged

#### Scenario: Idempotent replay

- **WHEN** the same Idempotency-Key and payload are retried after success
- **THEN** the original order is returned without creating a second order or consuming extra quota

#### Scenario: Idempotency conflict

- **WHEN** the same Idempotency-Key is reused with a different payload
- **THEN** the system returns conflict and creates no additional order

### Requirement: Customer order history isolation

Authenticated customers MUST list and retrieve only their own Test Meal orders, including status, payment status, package/menu, pricing breakdown, delivery window/date, address snapshot summary, and special instructions. Access to another customer's order MUST be denied (`404` or `403` per existing privacy convention).

#### Scenario: Owner can retrieve

- **WHEN** the owning customer requests their Test Meal detail by public id
- **THEN** the order details are returned

#### Scenario: Non-owner denied

- **WHEN** another customer requests that public id
- **THEN** the system denies access without exposing the order payload
