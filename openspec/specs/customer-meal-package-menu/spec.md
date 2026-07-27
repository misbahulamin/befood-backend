## Purpose

Authenticated verified customers can retrieve the full published monthly lunch and dinner menu for their active meal package(s), for calendar/planning UIs separate from reveal-gated today-menu.

## Requirements

### Requirement: Customer can retrieve full published monthly menu for their meal package
The system SHALL provide an authenticated verified-customer endpoint that returns the full published monthly lunch and dinner menu for each of the caller's active meal packages in the requested calendar month (default: current local month).

The response MUST include, per package: meal identity (`meal_public_id`, `meal_name`), `order_public_id`, `schedule_published`, and an ordered list of day slots with `service_date`, `meal_period` (`lunch` | `dinner`), and ingredient entries (`id`, `name`, `product_role`). The system MUST NOT apply today-menu reveal-time gating to this full-month response. The system MUST NOT return draft/unpublished schedule slot contents. The system MUST NOT expose another customer's orders or menus.

#### Scenario: Verified customer with published package menu
- **WHEN** a verified customer with a non-cancelled order for the target month requests their package menu and a published `MonthlyMenuSchedule` exists for that order's meal package and cycle month
- **THEN** the system responds `200` with that package in `packages`, `schedule_published` is `true`, and `days`/`slots` contain all published lunch and dinner assignments for the month ordered by date then period

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
