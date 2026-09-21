## ADDED Requirements

### Requirement: Mark delivered persists logistics audit for analytics
When an authorized admin or verified Delivery Man marks a `scheduled` `OrderDelivery` as meal `delivered`, the system MUST continue existing meal status, progress, wallet, and `marked_by` / `marked_at` behaviour, and MUST additionally persist logistics analytics fields available for that path: rider attribution when the actor is a Delivery Man (and documented rules when an admin marks on behalf of a zone), `delivered_at` aligned with completion time, optional completion coordinates from the request, activity-log `delivered` event, and daily-summary increments. Meal status vocabulary MUST NOT gain logistics-only values.

#### Scenario: Deliveryman mark writes attribution and activity
- **WHEN** a verified Delivery Man marks a scheduled stop in their zone as `delivered`
- **THEN** meal status becomes `delivered`, `marked_by`/`marked_at` are stored as today, rider attribution is stored, and a delivered activity event is recorded

#### Scenario: Admin skip does not count as completed delivery KPI
- **WHEN** an authorized admin marks a scheduled stop as `skipped`
- **THEN** meal status becomes `skipped` and completed-delivery KPI counters for riders MUST NOT increment for that stop

### Requirement: Deliveryman mark accepts optional completion coordinates
The Delivery Man mark-delivered API MUST accept optional `latitude` and `longitude` fields. When present and valid, they MUST be stored on the stop’s completion audit. When absent, mark behaviour MUST remain backward compatible with clients that only send `status` and optional `note`.

#### Scenario: Legacy mark payload still works
- **WHEN** a Delivery Man posts mark with `{ "status": "delivered" }` and no coordinates
- **THEN** the system responds successfully per existing mark rules and leaves completion coordinates null
