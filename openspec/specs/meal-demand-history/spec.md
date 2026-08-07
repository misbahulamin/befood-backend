## Purpose

Persist confirmed meal-demand snapshots and expose verified-admin historical reports that freeze counts and ingredient requirements at confirmation time.

## Requirements

### Requirement: Persist confirmed demand snapshots

The system SHALL persist historical meal demand snapshots keyed by `(service_date, meal_period, package)` (plus an optional overall rollup row or recomputable aggregate). Each snapshot MUST store at least: service date, meal period (`lunch`/`dinner`), package reference (nullable for overall), expected customer/meal count, meal-off count, final cooking count, ingredient requirement payload (structured list of ingredient id/name, unit, quantity), `confirmation_status` at write time, and timestamps (`captured_at`, and `confirmed_at` when status becomes confirmed). Snapshots MUST be written when a slot transitions to `confirmed` (meal-off deadline passed) via a controlled job or on-demand confirm-and-save path, and MUST be updatable only under documented rules to avoid duplicate divergent rows for the same key (upsert by unique key, not insert-only duplicates).

#### Scenario: Snapshot created after dinner deadline

- **WHEN** the dinner deadline for date `D` passes and the confirm-and-save process runs
- **THEN** the system stores a snapshot for `(D, dinner)` per package (and overall if used) with expected, meal-off, final cooking, ingredient requirements, `confirmation_status=confirmed`, and `confirmed_at` set

#### Scenario: No duplicate rows for same key

- **WHEN** the confirm-and-save process runs twice for the same `(D, dinner, package)`
- **THEN** the system updates the existing snapshot rather than creating a second row for that unique key

#### Scenario: Estimated live data is not required as history

- **WHEN** demand for a future dinner slot is still `estimated`
- **THEN** the system is not required to persist a final historical snapshot for that slot until confirmation

### Requirement: Admin meal history report API

The system SHALL provide a verified-admin historical report endpoint that lists or retrieves prior demand snapshots filtered by date range and optionally package and meal period. Each item MUST expose final cooking count, meal-off count, expected count, confirmation status, ingredient requirement summary, and capture/confirm timestamps. Live recalculation MUST NOT silently replace confirmed historical rows when the client requests history; history reads MUST return persisted snapshot values. Non-admin callers MUST be denied.

#### Scenario: Admin retrieves prior day history

- **WHEN** a verified admin requests history for `service_date=D` after snapshots were confirmed for lunch and dinner
- **THEN** the response includes both periods’ stored expected, meal-off, final cooking counts and ingredient requirements

#### Scenario: History filter by package

- **WHEN** a verified admin requests history filtered to Premium for a date range
- **THEN** only Premium package snapshots in that range are returned

#### Scenario: Customer denied history

- **WHEN** a verified customer calls the meal history endpoint
- **THEN** the system denies access with `401` or `403`

### Requirement: Snapshots support future analysis fields

Persisted snapshots MUST retain enough structured data for later business analysis, food-cost analysis, customer behavior (meal-off rates), and demand prediction without requiring reconstruction from mutable live deliveries alone. Ingredient requirement payloads MUST be frozen at capture time so later catalog price or yield edits do not rewrite historical quantities.

#### Scenario: Catalog yield change does not rewrite history

- **WHEN** a confirmed snapshot stored Rice at `135` kg and an admin later changes `customers_per_kg` on Rice
- **THEN** the historical snapshot still reports Rice quantity `135` kg
