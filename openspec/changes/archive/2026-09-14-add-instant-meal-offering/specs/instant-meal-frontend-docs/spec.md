## Purpose

Frontend and backend integration documentation for Instant Meal display and admin settings so client engineers can integrate without prior backend knowledge.

## ADDED Requirements

### Requirement: Frontend Instant Meal integration documentation

The system SHALL ship frontend documentation at `meals/docs/frontend/instant-meal-offering.md` that explains Instant Meal display integration. The document MUST include: base path and auth expectations, Instant Meal list endpoint, admin Instant settings endpoint, permissions matrix, field meanings for each Instant Meal card field, date-window behavior, ordering rules, how to render subscription upsell from `subscriber_price` with frontend-owned static copy, and an explicit note that Instant order/checkout is not available yet.

#### Scenario: Docs describe list-before-settings workflow for customers

- **WHEN** a frontend engineer reads the Instant Meal frontend docs
- **THEN** the docs explain calling the Instant Meal list API to render cards and optionally how admin UI loads/patches Instant settings

#### Scenario: Docs map card fields to API response keys

- **WHEN** a frontend engineer implements Instant Meal cards
- **THEN** the docs map `name`, `meal_period`, `service_date`, `package_name`, `price`, `image`, `ingredient_cost`, and `subscriber_price` to response fields with example JSON

### Requirement: Backend Instant Meal technical documentation

The system SHALL ship backend documentation at `meals/docs/backend/instant-meal-offering.md` covering models/settings used, pricing formula, isolation guarantees vs subscription snapshots, endpoint contracts, error cases (missing operational cost, empty window), and how to verify with tests or Swagger.

#### Scenario: Docs state non-breaking isolation rules

- **WHEN** a backend engineer reads the Instant Meal backend docs
- **THEN** the docs state that Instant pricing must not mutate published slot snapshots or cycle plan profit
