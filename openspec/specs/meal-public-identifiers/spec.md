## Purpose

Stable public UUID identity for meal packages (`MealCategory`) on customer-facing APIs, while retaining integer primary keys for internal relations.

## Requirements

### Requirement: MealCategory has a stable public UUID

The system SHALL store a unique, non-editable `public_id` UUID on every `MealCategory` while retaining the existing integer primary key for database relations. Existing rows MUST receive populated UUID values via migration without deleting or recreating meal data. New rows MUST receive a UUID automatically on create.

#### Scenario: Existing meal retains PK and gains public_id

- **WHEN** migrations run against a database that already contains `MealCategory` rows
- **THEN** each row keeps its integer primary key and gains a non-null unique `public_id`

#### Scenario: New meal receives public_id automatically

- **WHEN** a meal package is created through the API or ORM without supplying `public_id`
- **THEN** the saved row has a generated unique `public_id`

### Requirement: Public meal APIs identify meals by public_id

Public meal list and detail responses MUST expose read-only `public_id` and MUST NOT expose the integer primary key as `id`. Meal retrieve, update, and soft-delete endpoints MUST look up meals by `public_id` under `/meals/<public_id>/`. Requests that use a sequential integer path as if it were the public identifier MUST NOT resolve a meal successfully.

#### Scenario: List returns public_id instead of integer id

- **WHEN** a client calls `GET /meals/`
- **THEN** each meal object includes `public_id` and does not include integer `id`

#### Scenario: Detail by UUID succeeds

- **WHEN** a client calls `GET /meals/<public_id>/` with a valid meal UUID
- **THEN** the system returns that meal’s public detail payload

#### Scenario: Integer path no longer works as meal identity

- **WHEN** a client calls `GET /meals/3/` (or another integer) intending to use the old primary-key URL
- **THEN** the system does not return that meal as a successful public identity lookup (404 or equivalent not-found)

### Requirement: Public meal detail remains feature-complete without internal costing IDs

Public meal detail MUST continue to support listing-equivalent fields plus `description` and `current_cycle_offering` when a finalized plan exists. The public offering payload MUST include customer-safe menu and published price information and MUST NOT include internal `plan_id`, `product_cost`, or `profit`.

#### Scenario: Offering present without internal fields

- **WHEN** a public client retrieves a meal that has a finalized cycle plan
- **THEN** `current_cycle_offering` includes menu items and published totals/rates and omits `plan_id`, `product_cost`, and `profit`

#### Scenario: Unpriced or no finalized plan still works

- **WHEN** a public client retrieves a meal with no finalized offering
- **THEN** basic meal fields including `public_id` are returned and `current_cycle_offering` is null

### Requirement: Admin and manager meal tooling keep internal identifiers

Manager-authenticated meal create/update/delete and admin cycle tooling MAY continue to use integer primary keys and foreign keys for internal operations. Django admin MUST continue to manage `MealCategory` by integer PK and MAY display `public_id` as read-only.

#### Scenario: Soft delete still works via public_id URL

- **WHEN** a manager deletes a meal via `/meals/<public_id>/`
- **THEN** the meal is soft-deactivated (`is_active=False`) and the row remains in the database with the same integer PK and `public_id`

### Requirement: Customer order create references meal by public UUID

Customer order creation MUST accept meal identity as a UUID public identifier (`meal_public_id`) resolved to `MealCategory.public_id`. The system MUST reject unknown or inactive/unpriced meals with the same business rules as before.

#### Scenario: Order create with meal_public_id

- **WHEN** a verified customer submits an order with a valid `meal_public_id` for an active priced meal
- **THEN** the order is created against the corresponding `MealCategory` row

#### Scenario: Unknown meal_public_id rejected

- **WHEN** a customer submits an order with a UUID that does not match any meal
- **THEN** the request fails validation for the meal field

### Requirement: Frontend and API documentation describe the contract break

The change MUST document the public meal URL shape, response field rename (`id` → `public_id`), removed public offering fields, and order create field (`meal_public_id`) for frontend integrators.

#### Scenario: Frontend migration doc exists

- **WHEN** the change is implemented
- **THEN** `meals/docs/frontend/meal-public-uuid.md` describes the required client adjustments with request/response examples
