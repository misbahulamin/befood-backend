## ADDED Requirements

### Requirement: Customer current-month Onahar progress

The system SHALL provide an authenticated customer endpoint that returns the caller's current calendar-month Onahar progress, including at least: current points, target snapshot, contributions earned this month, remaining points to next contribution, and enough data for a progress UI (for example `32 / 50`). Unauthenticated callers MUST receive `401`. Customers MUST only see their own progress.

#### Scenario: Customer views progress below target

- **WHEN** an authenticated customer with 32 net points and target snapshot 50 requests their Onahar dashboard summary
- **THEN** the system responds `200` showing 32 current points, target 50, 0 contributions this month, and 18 points remaining to the next contribution

#### Scenario: Other customer data not visible

- **WHEN** customer A requests Onahar “me” resources
- **THEN** the response MUST contain only customer A's progress and MUST NOT expose another customer's identifiers or totals beyond public-safe ranking aggregates if included

### Requirement: Customer lifetime and history

The system SHALL provide authenticated customer views for lifetime eligible meals ordered (Onahar-credited), total Onahar meals contributed, current-month points, previous-month history rows, and current ranking when available. History rows MUST include month, eligible meals/net points, target, earned contributions, remaining/expired points, and contribution timing as applicable.

#### Scenario: Customer reads monthly history table

- **WHEN** an authenticated customer requests Onahar history after months with 54/50→1, 42/50→0, and 103/50→2
- **THEN** the paginated history MUST include those months with matching meals, targets, and contribution counts

#### Scenario: Unauthenticated history denied

- **WHEN** an unauthenticated client requests customer Onahar history
- **THEN** the system responds `401 Unauthorized`

### Requirement: Customer privacy preference

The system SHALL allow an authenticated customer to get and update their Onahar public display privacy preference among `public`, `partial`, and `anonymous`. The preference MUST control only public display naming; contribution amounts and system statistics remain visible per public transparency rules.

#### Scenario: Customer sets anonymous

- **WHEN** an authenticated customer PATCHes privacy preference to `anonymous`
- **THEN** subsequent public leaderboard/ledger entries for that customer MUST use an anonymous display label

#### Scenario: Invalid privacy value rejected

- **WHEN** an authenticated customer submits a privacy value outside the allowlist
- **THEN** the system MUST respond with a validation error and MUST leave the previous preference unchanged
