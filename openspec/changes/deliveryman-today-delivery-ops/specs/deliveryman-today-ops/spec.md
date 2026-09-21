## ADDED Requirements

### Requirement: Delivery Man can list today’s pending deliveries
The system SHALL provide a verified Delivery Man API to retrieve today’s pending (to-deliver) meal stops for the rider’s assigned zone and the server-resolved active meal period (meal-off business timezone). Default behavior MUST match the existing today-board contract: only `scheduled` stops, location-priority grouping, and no customer wallet balances.

#### Scenario: Pending board excludes delivered stops
- **WHEN** a verified Delivery Man requests today’s board without requesting delivered status
- **THEN** the response includes only `scheduled` deliveries in the assigned zone for the active meal period and MUST NOT include `delivered` stops

#### Scenario: Mark delivered removes stop from pending board
- **WHEN** the Delivery Man successfully marks a pending stop as delivered and then requests the pending board again
- **THEN** that delivery `public_id` MUST NOT appear in the pending board response

### Requirement: Delivery Man can list today’s delivered deliveries
The system SHALL allow a verified Delivery Man to retrieve today’s `delivered` stops for the same zone and active meal period scope as the pending board, using a documented query parameter or equivalent additive API mode. Completed stops MUST remain persisted on `OrderDelivery` (not deleted).

#### Scenario: Delivered board returns completed stops
- **WHEN** a verified Delivery Man requests today’s board filtered to delivered status after completing one or more stops
- **THEN** those delivered stops appear with customer identity, address/location fields, package/meal fields, and delivery timestamps when available

#### Scenario: Other zone delivered stops are excluded
- **WHEN** a Delivery Man requests today’s delivered board
- **THEN** deliveries belonging to customers outside the rider’s assigned zone MUST NOT be returned

### Requirement: Delivery Man can view today’s delivery summary metrics
The system SHALL provide a verified Delivery Man API that returns today’s assigned-scope counts for the active meal period: total stops, delivered count, and pending (`scheduled`) count. Counts MUST use the same zone, date, meal-period, and low-balance exclusion rules as the today board. The primary count unit MUST be `OrderDelivery` stops (not meal quantity), so pending + delivered equals total for the included statuses.

#### Scenario: Summary matches board math
- **WHEN** a rider’s zone has 10 in-scope stops for the active window of which 6 are delivered and 4 are scheduled
- **THEN** summary returns total 10, delivered 6, pending 4

#### Scenario: Rider cannot read another rider’s summary
- **WHEN** a verified Delivery Man calls the today-summary endpoint
- **THEN** metrics are computed only from that authenticated rider’s assigned zone scope (no other rider id parameter is accepted for cross-rider reads)

### Requirement: Today summary includes dynamic package breakdown
The system SHALL include a package breakdown in the today-summary response that groups in-scope stops by package identity derived from subscription/order package data (meal name snapshot and package public id when available). Package names MUST NOT be hardcoded. Breakdown counts MUST use the same stop-count unit as total/delivered/pending unless a separately documented quantity field is also returned.

#### Scenario: Packages grouped by snapshot name
- **WHEN** today’s in-scope stops include 5 Student Package, 3 Regular Package, and 2 Family Package stops
- **THEN** summary `packages` lists those names with counts 5, 3, and 2 (order may be documented)

#### Scenario: Empty board yields empty package list
- **WHEN** a rider has no in-scope stops for the active window
- **THEN** summary totals are zero and `packages` is an empty list

### Requirement: Board rows expose structured package fields without breaking existing clients
The system SHALL keep existing today-board customer-row fields (`meal_name`, `menu_items_label`, `status`, `meal_period`, `meal_quantity`, and address/identity fields) and SHALL add additive structured package fields (`package_name` and nullable `package_public_id`) sourced from the same package snapshot/relation used for `meal_name`. The system MUST NOT remove or rename existing fields in this change.

#### Scenario: Additive package fields present
- **WHEN** a Delivery Man fetches the today board for a subscription customer with meal name snapshot “Student Package”
- **THEN** the customer row includes `meal_name` “Student Package” and `package_name` “Student Package”, and may include `package_public_id` when the related meal category public id is available

#### Scenario: Menu items remain separate
- **WHEN** a stop has both a package snapshot and published menu ingredient labels
- **THEN** `package_name` / `meal_name` carry the package snapshot and `menu_items_label` carries the menu ingredients without requiring the backend to concatenate them into one field

### Requirement: Delivered rows expose completion attribution when available
For delivered board rows, the system SHALL expose completion time and Delivery Man attribution fields when stored on the delivery (prefer logistics `delivered_at` with fallback to `marked_at`; rider public id and display name from `delivered_by_rider` when set).

#### Scenario: Delivered row includes delivered_at after mark
- **WHEN** a Delivery Man marks a stop delivered and later loads the delivered board
- **THEN** that row includes a non-null delivered/marked timestamp field documented for clients

### Requirement: Zone authorization applies to all today-ops endpoints
The system SHALL enforce verified Delivery Man authentication and assigned-zone scope on pending board, delivered board, and today-summary endpoints. Mark-delivered MUST continue to reject deliveries outside the rider’s assigned zone.

#### Scenario: Foreign delivery mark rejected
- **WHEN** a Delivery Man posts mark-delivered for a delivery whose customer location is outside the assigned zone
- **THEN** the system responds `403 Forbidden` and does not change delivery status

#### Scenario: Unverified rider denied
- **WHEN** an authenticated user without verified Delivery Man access requests today-summary or today-board
- **THEN** the system responds `401` or `403` as appropriate

### Requirement: Today-ops date handling uses meal-off business timezone
The system SHALL resolve “today” and the active meal period using the existing meal-off timezone settings (Asia/Dhaka by default) and MUST ignore client-supplied service date or meal period overrides for these rider today-ops endpoints (same rule as the current today-board).

#### Scenario: Client date parameter ignored
- **WHEN** a Delivery Man passes a past `service_date` query parameter to today-board or today-summary
- **THEN** the response still uses the server-resolved business today and active meal period
