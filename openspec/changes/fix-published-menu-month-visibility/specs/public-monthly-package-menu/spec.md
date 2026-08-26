## ADDED Requirements

### Requirement: Public package menu exposes published-month discovery metadata

The system SHALL include `nearest_published_month` and `published_months` on every successful `200` response from `GET /meals/public-package-menu/` for an active meal package. `nearest_published_month` MUST be an object `{ "year": integer, "month": integer }` or `null` when no published schedule exists for that meal. `published_months` MUST be a sorted list (ascending by year then month) of `{ "year", "month" }` objects for all published schedules linked to the meal's cycle plans. When the requested `(year, month)` has a published schedule, `nearest_published_month` MUST equal that month. When the requested month is unpublished but another month is published, `nearest_published_month` MUST be the published month with the smallest calendar distance from the requested month, preferring a future month on ties. The system MUST NOT change `schedule_published`, `days`, or `meta` semantics for the requested month. Discovery metadata MUST be computed from published schedules only (draft schedules MUST NOT appear).

#### Scenario: Requested month published

- **WHEN** an unauthenticated client requests the public package menu for a meal and month that has a published `MonthlyMenuSchedule`
- **THEN** the response includes `schedule_published` true, `nearest_published_month` equal to the requested year/month, and that month listed in `published_months`

#### Scenario: Requested month unpublished but future month published

- **WHEN** an unauthenticated client requests August 2026 for Student Package and only September 2026 is published
- **THEN** the response includes `schedule_published` false, empty `days`, `nearest_published_month` `{ "year": 2026, "month": 9 }`, and `published_months` containing September 2026

#### Scenario: No published schedules

- **WHEN** an unauthenticated client requests any month for a meal with no published schedules
- **THEN** `nearest_published_month` is `null` and `published_months` is an empty list

#### Scenario: Multiple published months

- **WHEN** a meal has published schedules for July and September 2026 and the client requests August 2026
- **THEN** `published_months` lists both July and September in ascending order and `nearest_published_month` is July or September per the smallest-distance rule with future tie-break
