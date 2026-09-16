## ADDED Requirements

### Requirement: Admin can list customer subscriptions

The system SHALL provide a verified-admin web collection of `CustomerSubscription` rows, paginated, including active and cancelled records as filtered. Each list item MUST include customer reference, plan snapshots, `status`, `started_on`, cancel fields when present, and delivery progress summary for the current horizon. Unauthenticated callers MUST receive `401`. Authenticated non-admins MUST receive `403`.

#### Scenario: Admin lists subscriptions after customer subscribe

- **WHEN** a verified customer successfully subscribes and an authorized admin requests the admin subscription list
- **THEN** that subscription appears with plan snapshots, `status=active`, dates, and progress summary fields

#### Scenario: Customer denied admin list

- **WHEN** a verified customer requests the admin subscription list
- **THEN** the system responds `403 Forbidden`

### Requirement: Admin subscription filtering

The system SHALL support filtering admin subscriptions by `status` (`active` | `cancelled`), plan `public_id`, and date ranges (`started_on` / `cancelled_at`). Unsupported filter fields or invalid enums MUST be rejected with `400 Bad Request`.

#### Scenario: Filter active subscriptions

- **WHEN** an admin lists subscriptions with `status=active`
- **THEN** only `active` subscriptions are returned

#### Scenario: Filter by plan

- **WHEN** an admin lists subscriptions with a Premium plan `public_id`
- **THEN** only subscriptions whose plan is that package are returned

#### Scenario: Unsupported filter rejected

- **WHEN** an admin supplies an unknown filter field or invalid status
- **THEN** the system responds `400 Bad Request`

### Requirement: Admin subscription detail with deliveries

The system SHALL provide admin detail for a subscription `public_id` including customer reference, plan snapshots, status, period snapshot, expected/delivered/remaining counts for the generated horizon, and the delivery slot list (paginated or bounded). Mark-delivered on those slots MUST remain an admin/operator permission.

#### Scenario: Admin retrieves subscription detail

- **WHEN** an authorized admin retrieves a subscription by `public_id`
- **THEN** the response includes customer reference, snapshots, status, progress counters, and delivery slots
