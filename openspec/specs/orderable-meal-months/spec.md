## Purpose

Verified customers can load a lean list of selectable meal months (current through +12) with publish and existing-order flags for the Order Now month picker.

## Requirements

### Requirement: Customer can list orderable meal months for a meal package

The system SHALL provide an authenticated verified-customer endpoint that returns the selectable meal months for ordering a given meal package identified by `meal_public_id`. The list MUST include the current local calendar month and each of the next 12 months (13 entries). Each entry MUST include `year`, `month`, `order_month` (`YYYY-MM`), a display `label`, `is_current` (true only for the current local month), `is_published` (whether a published monthly menu schedule exists for that meal and month), and `has_order` (whether the caller already has a non-cancelled order for that `order_month`).

#### Scenario: Default window returned

- **WHEN** a verified customer requests orderable months for a valid `meal_public_id`
- **THEN** the system responds `200` with exactly 13 month entries starting at the current local month

#### Scenario: Current month flagged

- **WHEN** the orderable-months list is returned
- **THEN** exactly one entry has `is_current` true and that entry matches the current local year and month

#### Scenario: Published flag reflects schedule

- **WHEN** a published `MonthlyMenuSchedule` exists for the meal and a listed month
- **THEN** that entry’s `is_published` is `true`; months without a published schedule have `is_published` false

#### Scenario: Has order reflects caller lock

- **WHEN** the caller has a non-cancelled order for one listed `order_month`
- **THEN** that entry’s `has_order` is `true` and other months are `false` unless the caller also has orders there

#### Scenario: Missing meal rejected

- **WHEN** the client supplies an unknown `meal_public_id`
- **THEN** the system responds `404 Not Found`

#### Scenario: Unauthenticated request rejected

- **WHEN** an unauthenticated client requests orderable months
- **THEN** the system responds `401 Unauthorized`
