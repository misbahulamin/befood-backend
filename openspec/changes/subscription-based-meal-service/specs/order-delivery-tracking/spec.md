## MODIFIED Requirements

### Requirement: Expected delivery slots generated per package type

The system SHALL create expected `OrderDelivery` slots for each **active subscription** according to `meal_period_snapshot` and the rolling horizon in `subscription-delivery-continuity` (not according to `daily` / `weekly` / `monthly` purchase duration). Historical orders MAY keep previously generated slots. New service MUST NOT generate a closed month quota that completes the entitlement.

#### Scenario: Daily package gets one delivery slot

- **WHEN** a historical `daily` meal package order still exists
- **THEN** that historical order keeps its existing single delivery slot on `order_start_date`
- **AND** new customers MUST NOT purchase daily packages via order create

#### Scenario: Monthly package gets slots per calendar day and meal period

- **WHEN** an active subscription with `meal_period_snapshot=both` has a published menu for a 30-day month inside the rolling horizon
- **THEN** the system MUST create lunch and dinner slots for each day of that month in the horizon (60 slots for that month)
- **AND** filling that month MUST NOT complete or cancel the subscription

#### Scenario: Weekly package covers each day in the order window by meal period

- **WHEN** a historical weekly order still has an order window
- **THEN** historical slots remain as generated
- **AND** new weekly package purchases MUST NOT be created via customer order create

### Requirement: Mark delivery updates slot and progress

The system SHALL allow authorized admins (or kitchen operators with permission) to mark a scheduled delivery as `delivered` or `skipped`, and SHALL update subscription (or historical order) progress accordingly.

#### Scenario: Admin marks lunch delivered

- **WHEN** an authorized admin marks a `scheduled` delivery slot as `delivered`
- **THEN** the slot status MUST become `delivered`, progress counters MUST increase `delivered_count`, and an audit of who marked it MUST be stored

#### Scenario: Duplicate mark is idempotent or conflict-safe

- **WHEN** an admin marks a slot that is already `delivered`
- **THEN** the system MUST NOT create a second delivery event and MUST return a stable success or conflict response without corrupting counts

#### Scenario: Customer cannot mark delivery by default

- **WHEN** a customer calls a mark-delivery endpoint without admin/operator permission
- **THEN** the system MUST respond with `403 Forbidden` (or hide the route from customer clients)

### Requirement: Active days in current month

The system SHALL expose which service dates in the current calendar month remain relevant (scheduled or delivered) for an active subscription.

#### Scenario: Monthly package week/day activity for current month

- **WHEN** an admin or owning customer requests progress for an active subscription in the current month
- **THEN** the response MUST include expected total for generated slots, delivered count, remaining count, and the set or list of active/relevant dates within the current month window

## REMOVED Requirements

### Requirement: Daily close after one delivery

**Reason:** Daily one-shot packages are not the customer subscription model; an active subscription must not close after a single delivery.
**Migration:** Historical daily orders may still complete. New service uses open-ended `CustomerSubscription`.
