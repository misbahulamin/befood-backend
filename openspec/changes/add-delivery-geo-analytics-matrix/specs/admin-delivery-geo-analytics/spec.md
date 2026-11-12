# Spec Delta

## Purpose

Verified-admin date-range analytics for delivery geography so ops can compare customer density, churn, meal volume, and rider workload across Zone → Location → Sub-location.

## ADDED Requirements

### Requirement: Geo analytics matrix endpoint
The system SHALL provide a verified-admin web API that returns a hierarchical analytics matrix for a required inclusive date range `from` and `to` (Asia/Dhaka calendar dates). Unauthenticated callers MUST receive `401`. Authenticated non-admins MUST receive `403`. Missing or invalid dates, inverted ranges, unknown query keys, or ranges longer than 366 days MUST yield `400`.

#### Scenario: Valid matrix request
- **WHEN** a verified admin requests the geo matrix with valid `from` and `to` within 366 days
- **THEN** the response is `200` and includes period bounds plus a zone → location → sub-location hierarchy with metric nodes

#### Scenario: Missing date range rejected
- **WHEN** a verified admin omits `from` or `to`
- **THEN** the system responds `400 Bad Request`

#### Scenario: Non-admin denied
- **WHEN** an authenticated non-admin requests geo analytics
- **THEN** the system responds `403 Forbidden`

### Requirement: Customer density metrics per geo node
Each matrix node MUST include assigned customer counts for the current operational assignment (derived from customer delivery sub-location → location → zone), including totals and lifecycle splits for at least active, at_risk, unsubscribed, and never_subscribed when classification is available. Nodes with zero assigned customers MAY still appear for active zones/locations/sub-locations that exist in the hierarchy, or be omitted when documented as sparse mode—either way MUST be consistent and documented.

#### Scenario: Zone with mixed lifecycle customers
- **WHEN** Zone 1 has customers classified as active, at_risk, and unsubscribed
- **THEN** Zone 1’s customer metrics include separate counts for those lifecycle values

#### Scenario: Unassigned customers bucket
- **WHEN** some customers have no delivery sub-location
- **THEN** the matrix payload includes an unassigned customer count separate from zone nodes

### Requirement: Period churn metrics per geo node
For the requested period, each geo node MUST include churned customer count attributed by the customer’s operational geography at query time (or documented snapshot rule), and a churn rate percent using an active-at-period-start base scoped to that node when the base is greater than zero (otherwise `0`).

#### Scenario: Location churn concentration
- **WHEN** five customers assigned under Chawkbazar churn in the period and twenty were active there at period start
- **THEN** Chawkbazar reports churned_count 5 and churn_rate_percent 25.00

#### Scenario: Zero base yields zero rate
- **WHEN** a sub-location had no active customers at period start but records a cancel attributed there
- **THEN** churn_rate_percent for that node is 0 and churned_count still reflects the cancels

### Requirement: Period meal delivery volume per geo node
For the requested period, each geo node MUST include meal delivery counts for scheduled, delivered, skipped, and missed (and total) attributed by the delivery’s logistics/customer sub-location hierarchy. Optional `meal_period=lunch|dinner` MUST filter volume when provided; when omitted, counts MUST include both periods. Day-scoped ops summary behavior MUST remain unchanged.

#### Scenario: Sub-location meal volume
- **WHEN** Gate A has 40 delivered and 5 skipped meals in the period
- **THEN** Gate A volume metrics show delivered 40, skipped 5, and total at least 45

#### Scenario: Lunch-only volume filter
- **WHEN** a verified admin requests the matrix with `meal_period=lunch`
- **THEN** volume metrics include only lunch deliveries for the period

### Requirement: Delivery man workload on zone nodes
Zone-level matrix nodes MUST include the primary assigned delivery man’s identity summary when set, plus period workload counts (at least delivered and total meals) for that zone. Zones without a rider MUST still return volume metrics and mark the rider as null or an unassigned-zone workload indicator.

#### Scenario: Assigned rider workload
- **WHEN** Zone 1 is assigned to Delivery Man Rahim and has 120 delivered meals in the period
- **THEN** Zone 1 includes Rahim’s identity summary and workload delivered count 120

### Requirement: Ranking and comparative summaries
The system SHALL expose ranking or comparative sections (same response or documented sibling endpoint) for highest and lowest customer density, highest churn rate (with minimum active-base threshold documented), highest meal volume, and unassigned customer/delivery counts for the period.

#### Scenario: High and low density lists
- **WHEN** multiple locations have different assigned customer totals
- **THEN** the rankings include the highest-density and lowest-density locations among eligible nodes

#### Scenario: Churn ranking respects minimum base
- **WHEN** a location has churn rate 100% but active-at-start base below the documented minimum threshold
- **THEN** that location MUST NOT appear in highest-churn ranking (or MUST be flagged as statistically excluded per docs)

### Requirement: Optional hierarchy filters
The system SHALL allow optional allowlisted filters `zone_public_id`, `location_public_id`, and `sub_location_public_id` to restrict the matrix to a subtree. Unknown UUIDs MUST yield `404` or an empty scoped matrix with `200`—behavior MUST be documented and consistent.

#### Scenario: Filter to one zone
- **WHEN** a verified admin requests the matrix with `zone_public_id` for Zone 1
- **THEN** only Zone 1 (and its locations/sub-locations) appear in the hierarchy
