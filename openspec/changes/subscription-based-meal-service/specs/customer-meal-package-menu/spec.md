## MODIFIED Requirements

### Requirement: Customer can retrieve full published monthly menu for their meal package

The system SHALL provide an authenticated verified-customer endpoint that returns the full published monthly lunch and dinner menu for the caller’s **active subscription** plan in the requested calendar month (default: current local month).

The response MUST include, per package: meal identity (`meal_public_id`, `meal_name`), `subscription_public_id` (historical responses MAY still include `order_public_id`), `schedule_published`, and an ordered list of day slots with `service_date`, `meal_period` (`lunch` | `dinner`), and ingredient entries (`id`, `name`, `product_role`). Each ingredient’s `product_role` MUST come from the linked meal package’s `MealCyclePlanLine` for that cycle. The system MUST omit ingredients with `is_customer_visible=false`. The system MUST NOT apply today-menu reveal-time gating to this full-month response. The system MUST NOT return draft/unpublished schedule slot contents. The system MUST NOT expose another customer's subscriptions or menus.

This ownership-scoped package-menu endpoint remains the post-subscribe calendar path. Browsing a published menu by `meal_public_id` without an active subscription is provided by the existing preview endpoint and MUST NOT weaken this endpoint’s ownership scoping.

#### Scenario: Verified customer with published package menu

- **WHEN** a verified customer with an active subscription requests their package menu for a month that has a published `MonthlyMenuSchedule` for that plan
- **THEN** the system responds `200` with that package in `packages`, `schedule_published` is `true`, and `days`/`slots` contain all published lunch and dinner assignments for the month ordered by date then period

#### Scenario: Role comes from package plan not catalog

- **WHEN** Vegetable is `side` on the customer’s package plan and appears on a published slot
- **THEN** the package-menu ingredient entry for Vegetable has `product_role` `side`

#### Scenario: Non-visible ingredient omitted

- **WHEN** a published slot includes an ingredient with `is_customer_visible=false`
- **THEN** that ingredient is absent from the customer package-menu slot list

#### Scenario: Package exists but menu not published

- **WHEN** a verified customer has an active subscription but no published schedule exists for that meal/cycle month
- **THEN** the system responds `200` with the package identity, `schedule_published` is `false`, and the day/slot list is empty

#### Scenario: No active meal package

- **WHEN** a verified customer has no active subscription
- **THEN** the system responds `200` with an empty `packages` list

#### Scenario: Unauthenticated request rejected

- **WHEN** an unauthenticated client requests the package menu
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Customer cannot read another package by guessing meal id

- **WHEN** a verified customer requests the package menu
- **THEN** the system resolves menus only from that customer's own active subscription and does not accept an arbitrary meal/package identifier as sufficient authorization to view a menu they do not own

#### Scenario: Pre-order preview does not replace ownership-scoped package menu

- **WHEN** a verified customer has no active subscription but a published schedule exists for a meal
- **THEN** `GET /meals/my-package-menu/` for that month still returns an empty `packages` list, while the menu preview endpoint may return that meal’s published menu

### Requirement: Optional month selection is validated and ownership-scoped

The system SHALL accept optional `year` and `month` query parameters to select the calendar month. When omitted, the system MUST use the current local month. Invalid or incomplete year/month input MUST be rejected with `400 Bad Request`. Results MUST still be limited to the authenticated customer's **active subscription** plan for that month (not a monthly order row).

#### Scenario: Explicit year and month

- **WHEN** a verified customer with an active subscription requests the package menu with valid `year` and `month` query parameters
- **THEN** the system returns that subscribed plan’s published menu for that month when published

#### Scenario: Invalid month query

- **WHEN** a client supplies an invalid `month` (outside 1–12) or only one of `year`/`month`
- **THEN** the system responds `400 Bad Request`

### Requirement: Customer can preview a published monthly menu before ordering

The system SHALL provide an authenticated verified-customer endpoint to preview the published monthly lunch and dinner menu for a meal package identified by `meal_public_id` and a calendar `year`/`month`, without requiring the caller to already own a subscription. When a published `MonthlyMenuSchedule` exists, the response MUST include meal identity, `schedule_published: true`, and day slots with the same ingredient visibility and `product_role` rules as the existing customer package-menu capability (omit `is_customer_visible=false`; role from plan lines). When no published schedule exists, the system MUST respond successfully with `schedule_published: false` and an empty day/slot list so clients can show a friendly “menu not published yet” message. The system MUST NOT apply today-menu reveal-time gating. The system MUST NOT expose another customer’s subscriptions.

#### Scenario: Preview published menu without existing order

- **WHEN** a verified customer requests the menu preview for a meal and month that has a published schedule, and the customer has no active subscription
- **THEN** the system responds `200` with `schedule_published` true and the published day/slot contents

#### Scenario: Preview unpublished month

- **WHEN** a verified customer requests the menu preview for a meal and month with no published schedule
- **THEN** the system responds `200` with `schedule_published` false and an empty day/slot list

#### Scenario: Invalid month query on preview

- **WHEN** a client supplies an invalid `month` or only one of `year`/`month`
- **THEN** the system responds `400 Bad Request`

#### Scenario: Unknown meal on preview

- **WHEN** a client supplies an unknown `meal_public_id`
- **THEN** the system responds `404 Not Found`

#### Scenario: Unauthenticated preview rejected

- **WHEN** an unauthenticated client requests the menu preview
- **THEN** the system responds `401 Unauthorized`
