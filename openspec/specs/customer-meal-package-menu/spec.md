## Purpose

Authenticated verified customers can retrieve the full published monthly lunch and dinner menu for their active meal package(s), for calendar/planning UIs separate from reveal-gated today-menu. Pre-order browsing of a published menu by meal package (without an existing order) is provided by a separate order-menu preview endpoint.

## Requirements

### Requirement: Customer can retrieve full published monthly menu for their meal package

The system SHALL provide an authenticated verified-customer endpoint that returns the full published monthly lunch and dinner menu for each of the caller's active meal packages in the requested calendar month (default: current local month).

The response MUST include, per package: meal identity (`meal_public_id`, `meal_name`), `order_public_id`, `schedule_published`, and an ordered list of day slots with `service_date`, `meal_period` (`lunch` | `dinner`), and ingredient entries (`id`, `name`, `product_role`). Each ingredient’s `product_role` MUST come from the linked meal package’s `MealCyclePlanLine` for that cycle. The system MUST omit ingredients with `is_customer_visible=false`. The system MUST NOT apply today-menu reveal-time gating to this full-month response. The system MUST NOT return draft/unpublished schedule slot contents. The system MUST NOT expose another customer's orders or menus.

This ownership-scoped package-menu endpoint remains the post-order calendar path. Pre-order browsing of a published menu by `meal_public_id` without an existing order is provided by the separate order-menu preview endpoint and MUST NOT weaken this endpoint’s ownership scoping.

#### Scenario: Verified customer with published package menu

- **WHEN** a verified customer with a non-cancelled order for the target month requests their package menu and a published `MonthlyMenuSchedule` exists for that order's meal package and cycle month
- **THEN** the system responds `200` with that package in `packages`, `schedule_published` is `true`, and `days`/`slots` contain all published lunch and dinner assignments for the month ordered by date then period

#### Scenario: Role comes from package plan not catalog

- **WHEN** Vegetable is `side` on the customer’s package plan and appears on a published slot
- **THEN** the package-menu ingredient entry for Vegetable has `product_role` `side`

#### Scenario: Non-visible ingredient omitted

- **WHEN** a published slot includes an ingredient with `is_customer_visible=false`
- **THEN** that ingredient is absent from the customer package-menu slot list

#### Scenario: Package exists but menu not published

- **WHEN** a verified customer has an active order for the target month but no published schedule exists for that meal/cycle
- **THEN** the system responds `200` with the package identity, `schedule_published` is `false`, and the day/slot list is empty

#### Scenario: No active meal package

- **WHEN** a verified customer has no non-cancelled order for the target month
- **THEN** the system responds `200` with an empty `packages` list

#### Scenario: Unauthenticated request rejected

- **WHEN** an unauthenticated client requests the package menu
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Customer cannot read another package by guessing meal id

- **WHEN** a verified customer requests the package menu
- **THEN** the system resolves menus only from that customer's own orders and does not accept an arbitrary meal/package identifier as sufficient authorization to view a menu they do not own

#### Scenario: Pre-order preview does not replace ownership-scoped package menu

- **WHEN** a verified customer has no order for a month but a published schedule exists for a meal
- **THEN** `GET /meals/my-package-menu/` for that month still returns an empty `packages` list, while the order-menu preview endpoint may return that meal’s published menu

### Requirement: Optional month selection is validated and ownership-scoped
The system SHALL accept optional `year` and `month` query parameters to select the calendar month. When omitted, the system MUST use the current local month. Invalid or incomplete year/month input MUST be rejected with `400 Bad Request`. Results MUST still be limited to the authenticated customer's orders for that month.

#### Scenario: Explicit year and month
- **WHEN** a verified customer requests the package menu with valid `year` and `month` query parameters
- **THEN** the system returns packages and published menus for that customer's orders in that month

#### Scenario: Invalid month query
- **WHEN** a client supplies an invalid `month` (outside 1–12) or only one of `year`/`month`
- **THEN** the system responds `400 Bad Request`

### Requirement: Full package menu stays separate from today-menu reveal rules
The system SHALL keep `GET /meals/today-menu/` behavior unchanged, including reveal-time gating for today's lunch and dinner. The full package menu endpoint MUST remain a separate read path for calendar browsing.

#### Scenario: Today-menu unchanged
- **WHEN** a verified customer calls `today-menu` after the full package menu endpoint exists
- **THEN** today-menu still returns only currently revealed periods for today according to reveal settings

### Requirement: Customer can preview a published monthly menu before ordering

The system SHALL provide an authenticated verified-customer endpoint to preview the published monthly lunch and dinner menu for a meal package identified by `meal_public_id` and a calendar `year`/`month`, without requiring the caller to already own an order for that month. When a published `MonthlyMenuSchedule` exists, the response MUST include meal identity, `schedule_published: true`, and day slots with the same ingredient visibility and `product_role` rules as the existing customer package-menu capability (omit `is_customer_visible=false`; role from plan lines). When no published schedule exists, the system MUST respond successfully with `schedule_published: false` and an empty day/slot list so clients can show a friendly “menu not published yet” message. The system MUST NOT apply today-menu reveal-time gating. The system MUST NOT expose another customer’s orders.

#### Scenario: Preview published menu without existing order

- **WHEN** a verified customer requests the order-menu preview for a meal and month that has a published schedule, and the customer has no order for that month
- **THEN** the system responds `200` with `schedule_published` true and the published day/slot contents

#### Scenario: Preview unpublished month

- **WHEN** a verified customer requests the order-menu preview for a meal and month with no published schedule
- **THEN** the system responds `200` with `schedule_published` false and an empty day/slot list

#### Scenario: Invalid month query on preview

- **WHEN** a client supplies an invalid `month` or only one of `year`/`month`
- **THEN** the system responds `400 Bad Request`

#### Scenario: Unknown meal on preview

- **WHEN** a client supplies an unknown `meal_public_id`
- **THEN** the system responds `404 Not Found`

#### Scenario: Unauthenticated preview rejected

- **WHEN** an unauthenticated client requests the order-menu preview
- **THEN** the system responds `401 Unauthorized`
