## ADDED Requirements

### Requirement: OrderDelivery stores a resolved address snapshot
When the system creates an `OrderDelivery` row, it MUST resolve the customer’s effective delivery place for that `service_date` and `meal_period` and MUST persist snapshot fields on the delivery (at minimum label and full address; area/city and coordinates when available). The system MAY store a nullable FK to the source delivery place with `ON DELETE SET NULL`. Snapshot text MUST remain available for ops and customers even if the place is later edited or deleted.

#### Scenario: New delivery gets snapshot at creation
- **WHEN** order expansion creates a lunch delivery for a service date
- **THEN** that `OrderDelivery` row stores the resolved lunch destination snapshot for that date

#### Scenario: Lunch and dinner on same day may differ
- **WHEN** a customer’s lunch resolves to Office and dinner resolves to Home on the same service date
- **THEN** the lunch delivery snapshot refers to Office and the dinner delivery snapshot refers to Home

### Requirement: Historical deliveries do not rewrite on preference change
After an `OrderDelivery` leaves a purely future-editable state, preference changes MUST NOT alter its address snapshot. For future rows still in `scheduled` status, the system MAY re-resolve and update snapshots when the customer changes preferences or places (automatic resync on preference save is allowed and recommended).

#### Scenario: Delivered row immutable address
- **WHEN** a delivery is already `delivered` and the customer later changes the lunch default place
- **THEN** that delivered row’s address snapshot remains unchanged

#### Scenario: Future scheduled row can resync
- **WHEN** a customer changes dinner preference and has future `scheduled` dinner deliveries
- **THEN** those future scheduled dinners MAY be updated to the newly resolved snapshot

### Requirement: Delivery reads expose destination to authorized clients
Customer and authorized ops delivery representations MUST include the stored destination snapshot fields needed to fulfill the meal. The system MUST NOT expose another customer’s deliveries or destinations. Public identity for deliveries remains `public_id`.

#### Scenario: Customer sees where a slot will be delivered
- **WHEN** an authenticated customer retrieves an owned upcoming delivery
- **THEN** the response includes the delivery address snapshot for that slot

#### Scenario: Foreign delivery hidden
- **WHEN** an authenticated customer requests a delivery `public_id` belonging to another customer
- **THEN** the system responds `404 Not Found`

### Requirement: Legacy customers receive a migrated default destination
For existing customers who only have a present default delivery address, the system MUST backfill a delivery place and lunch/dinner preferences (or equivalent fallback) so new `OrderDelivery` rows can resolve a destination without mandatory re-onboarding.

#### Scenario: Backfill from present default
- **WHEN** migration runs for a customer with a present `is_default_delivery` address and no delivery places yet
- **THEN** the system creates a delivery place from that address and sets it as the effective lunch and dinner default (or documented equivalent fallback)
