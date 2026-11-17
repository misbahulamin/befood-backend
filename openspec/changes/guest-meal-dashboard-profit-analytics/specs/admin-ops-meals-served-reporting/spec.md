# Spec Delta

## Purpose

Provide Admin ops dashboard meals-served KPIs that count delivered food boxes for regular and Guest Meals separately and as a combined total, while keeping delivery-stop counts distinct.

## ADDED Requirements

### Requirement: Total meals served includes delivered guest boxes
The Admin ops dashboard summary MUST expose delivered food-box metrics such that `total_meals_served = regular_meals_served + guest_meals_served`. `regular_meals_served` MUST count delivered regular subscription meal boxes. `guest_meals_served` MUST sum delivered Guest Meal `quantity` values. Scheduled and cancelled Guest Meals MUST NOT contribute.

#### Scenario: One stop with two guest boxes
- **WHEN** there is one delivered regular meal and one delivered Guest Meal order with quantity `2` for the same stop
- **THEN** `regular_meals_served` includes `1`, `guest_meals_served` includes `2`, and `total_meals_served` includes `3`

#### Scenario: Scheduled guest boxes excluded
- **WHEN** a Guest Meal order is still `scheduled`
- **THEN** its quantity is not included in `guest_meals_served` or `total_meals_served`

### Requirement: Monthly and today meals served use service date
Month-to-date and today food-box served metrics MUST filter by Asia/Dhaka business `service_date` bounds, not Guest Meal purchase `created_at`. Existing `monthly_meals_served` and any new regular/guest/total month or today food-box fields MUST follow the same date rule.

#### Scenario: Guest purchased earlier but served later
- **WHEN** a Guest Meal is purchased on an earlier calendar day for today’s service date and is delivered today
- **THEN** today’s guest meals served includes that delivered quantity and the purchase day does not receive the served count

### Requirement: Today delivery remains a delivery-stop metric
The existing `today_delivery` field MUST continue to mean delivered delivery stops for today, not food-box quantity. Additional guest boxes on the same stop MUST NOT inflate `today_delivery`.

#### Scenario: Guest boxes do not increase stop count
- **WHEN** one delivery stop is delivered today with regular quantity `1` and guest quantity `2`
- **THEN** `today_delivery` remains `1` while today total food boxes served is `3`

### Requirement: Additive meals-served fields preserve compatibility
The system MUST preserve existing dashboard field names consumed by clients and add regular/guest/total meals-served breakdowns additively. Stop vs food-box semantics for `today_delivery` MUST remain unambiguous.

#### Scenario: Clients can read regular and guest breakdowns
- **WHEN** an authorized admin loads the ops dashboard summary after guest-aware aggregation ships
- **THEN** the response includes distinguishable regular, guest, and total meals-served values for lifetime and current month scopes used by the dashboard

#### Scenario: Stop metric remains available beside food-box totals
- **WHEN** `total_meals_served` reports food boxes and a stop was delivered with extra guest boxes
- **THEN** clients can still read today’s delivery-stop count via `today_delivery` without treating guest boxes as extra stops
