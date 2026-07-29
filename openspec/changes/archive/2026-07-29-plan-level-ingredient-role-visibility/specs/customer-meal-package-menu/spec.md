## MODIFIED Requirements

### Requirement: Customer can retrieve full published monthly menu for their meal package

The system SHALL provide an authenticated verified-customer endpoint that returns the full published monthly lunch and dinner menu for each of the caller's active meal packages in the requested calendar month (default: current local month).

The response MUST include, per package: meal identity (`meal_public_id`, `meal_name`), `order_public_id`, `schedule_published`, and an ordered list of day slots with `service_date`, `meal_period` (`lunch` | `dinner`), and ingredient entries (`id`, `name`, `product_role`). Each ingredient’s `product_role` MUST come from the linked meal package’s `MealCyclePlanLine` for that cycle. The system MUST omit ingredients with `is_customer_visible=false`. The system MUST NOT apply today-menu reveal-time gating to this full-month response. The system MUST NOT return draft/unpublished schedule slot contents. The system MUST NOT expose another customer's orders or menus.

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
