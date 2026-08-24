## ADDED Requirements

### Requirement: Verified customer can subscribe to one available plan

The system SHALL allow an authenticated verified customer to create a subscription by submitting a subscribable plan `public_id`. On success the system MUST persist a `CustomerSubscription` with `status=active`, opaque `public_id`, `started_on` equal to the current local business date (meal-off timezone), and snapshots of `meal_name` and `meal_period` from the plan at subscribe time. The response MUST be `201 Created`. Subscribe MUST NOT create a month-bounded `Order`. Unauthenticated callers MUST receive `401`. Unverified customers MUST be rejected.

#### Scenario: Successful subscribe

- **WHEN** a verified customer with no active subscription and a passing wallet gate subscribes to an active subscribable plan
- **THEN** the system creates an `active` subscription, snapshots the plan name and meal period, and does not create a new monthly `Order`

#### Scenario: Unknown or inactive plan rejected

- **WHEN** the client submits a plan `public_id` that is unknown, inactive, or not subscribable
- **THEN** the system rejects the request (`404` or `422`) and creates no subscription

#### Scenario: Unauthenticated subscribe rejected

- **WHEN** an unauthenticated client posts subscribe
- **THEN** the system responds `401 Unauthorized`

### Requirement: At most one active subscription per customer

The system SHALL allow a customer at most one subscription whose `status` is `active`. A second subscribe attempt MUST be rejected without creating a row. A cancelled subscription MUST NOT block a later subscribe to the same or a different plan. Enforcement MUST live in the subscribe service (not only the HTTP layer) and MUST be backed by a database uniqueness constraint on active rows.

#### Scenario: Second active subscribe rejected

- **WHEN** a customer already has an `active` subscription and attempts to subscribe again
- **THEN** the system rejects with a conflict/validation error and persists no second active subscription

#### Scenario: Subscribe after cancel allowed

- **WHEN** the customer’s only subscription is `cancelled` and they subscribe to an available plan
- **THEN** the system creates a new `active` subscription

### Requirement: Customer can read current subscription status

The system SHALL expose the caller’s current active subscription (or a null payload when none). Detail MUST include `public_id`, plan identity and snapshots, `status`, `started_on`, and cancel fields when cancelled. A customer MUST NOT read another customer’s subscription (`404` or `403`).

#### Scenario: Current returns active subscription

- **WHEN** a verified customer with an active subscription requests current
- **THEN** the system responds `200` with that subscription’s public fields

#### Scenario: Current is null when none

- **WHEN** a verified customer has no active subscription
- **THEN** the current endpoint returns a null subscription payload with a clear message

#### Scenario: Foreign subscription hidden

- **WHEN** a verified customer requests a `public_id` owned by another customer
- **THEN** the system responds `404` or `403` without leaking the payload

### Requirement: Customer can cancel an active subscription

The system SHALL allow the owning verified customer to cancel their active subscription. On success the system MUST set `status=cancelled`, record `cancelled_at`, and set `cancel_effective_on` to the current local business date. Scheduled delivery slots with `service_date` after that date MUST be marked `skipped` with a system/subscription-cancel skip source so they are not cooked. Slots with `service_date` on or before `cancel_effective_on` MUST remain unchanged so today’s remaining periods still follow meal-off rules. Cancel MUST be idempotent: cancelling an already-cancelled own subscription MUST NOT error as a conflict that implies a different owner.

#### Scenario: Cancel stops future slots

- **WHEN** a customer cancels an active subscription that has scheduled slots tomorrow and later
- **THEN** the subscription is `cancelled` and those future scheduled slots become `skipped`

#### Scenario: Today’s slots remain after cancel

- **WHEN** a customer cancels on date `D` and has a still-`scheduled` dinner on `D`
- **THEN** that dinner slot is not auto-skipped by cancel

#### Scenario: Other customer cannot cancel

- **WHEN** a verified customer attempts to cancel another customer’s subscription
- **THEN** the system responds `404` or `403` and leaves the subscription active

### Requirement: Customer monthly order create is retired

The system MUST reject verified-customer meal package order creation that starts new monthly service (`POST` create with optional `year`/`month`). The rejection MUST use a stable documented error that directs clients to subscribe. The system MUST NOT persist a new `Order` from that path. Historical order list/detail MAY remain read-only.

#### Scenario: Order create after subscription launch rejected

- **WHEN** a verified customer posts the legacy meal-order create endpoint
- **THEN** the system rejects the request with a subscribe-required error and creates no `Order`
