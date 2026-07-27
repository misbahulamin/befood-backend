## ADDED Requirements

### Requirement: Permanent assets are modeled separately from food inventory

The system SHALL store permanent (non-consumable) assets in a dedicated catalog that is independent of meal ingredients, meal cycles, and order fulfillment. Permanent assets MUST NOT decrease in quantity as a side effect of cooking, packaging, or order processing. The catalog MUST support classification via asset categories and individual permanent asset records identified by opaque `public_id` values.

#### Scenario: Asset exists without ingredient linkage

- **WHEN** a permanent asset record is created for kitchen equipment such as a refrigerator
- **THEN** the system stores it without requiring or creating any `Ingredient` or meal-cycle association

#### Scenario: Cooking does not consume assets

- **WHEN** meals are planned, costed, or ordered in the existing meal/order modules
- **THEN** permanent asset quantities and statuses MUST remain unchanged as a result of those operations

### Requirement: Asset categories classify permanent items

The system SHALL provide asset categories with at least: unique name, `public_id`, optional description, `is_active`, and timestamps. Default seed categories MUST include Kitchen Equipment, Furniture, Lighting, Computer Equipment, and Other. Verified admins MUST be able to create additional active categories for items such as large korai, rice cookers, or office equipment groupings.

#### Scenario: Seed categories available

- **WHEN** the module is installed and migrated
- **THEN** the five default categories exist and are active

#### Scenario: Custom category

- **WHEN** a verified admin creates a category named "Large Cookware"
- **THEN** the system persists it with a new `public_id` and allows assets to reference it

#### Scenario: Duplicate category name rejected

- **WHEN** a verified admin attempts to create a category whose name already exists (case-sensitive uniqueness as implemented)
- **THEN** the system returns a validation error and does not create a duplicate

### Requirement: Permanent asset records capture identity and ops metadata

Each permanent asset MUST include: `public_id`, human-readable `name`, required category, unique `asset_tag`, `status`, `quantity` (integer ≥ 1, default 1), optional `serial_number`, optional `brand`, optional `model`, optional outlet location, optional `purchase_date`, optional `purchase_cost` (exact decimal), optional `currency` (default `BDT`), optional `warranty_until`, optional `notes`, `is_active`, and `created_at` / `updated_at`.

#### Scenario: Register a refrigerator

- **WHEN** a verified admin creates an asset named "Walk-in Refrigerator", category Kitchen Equipment, `asset_tag` "KE-REF-001", `quantity` 1, status `in_service`
- **THEN** the system returns the asset with a `public_id` and persists the provided fields

#### Scenario: Batch of chairs

- **WHEN** a verified admin creates an asset for identical chairs with `quantity` 12 and a single batch `asset_tag`
- **THEN** the system accepts `quantity` 12 and does not require twelve separate rows

#### Scenario: Reject invalid quantity

- **WHEN** a create or update sets `quantity` to 0 or a negative number
- **THEN** the system returns a validation error

#### Scenario: Reject duplicate asset_tag

- **WHEN** a verified admin creates an asset with an `asset_tag` that already exists
- **THEN** the system returns a validation error and does not create the asset

### Requirement: Asset status lifecycle is explicit

Each permanent asset MUST have a `status` from the allowlist: `in_service`, `under_maintenance`, `retired`, `disposed`. The system MUST reject unknown status values. Soft deactivation via `is_active=false` MUST be supported so historical records remain queryable when inactive inclusion is requested.

#### Scenario: Mark under maintenance

- **WHEN** a verified admin sets an in-service gas burner to `under_maintenance`
- **THEN** the asset status becomes `under_maintenance` and the record remains active unless `is_active` is also cleared

#### Scenario: Dispose asset

- **WHEN** a verified admin sets status to `disposed` and `is_active` to false
- **THEN** the asset is excluded from the default active list and retained for history

#### Scenario: Reject unknown status

- **WHEN** a create or update submits `status` "broken" (not in the allowlist)
- **THEN** the system returns a validation error

### Requirement: Optional outlet location without inventing company/branch

A permanent asset MAY reference an existing `Outlet` as its location. Absence of an outlet MUST mean site-unspecified / shared. The system MUST NOT require company or branch entities that do not exist in the current domain model.

#### Scenario: Asset assigned to main outlet

- **WHEN** a verified admin creates or updates an asset with a valid outlet reference
- **THEN** the asset is stored with that outlet as its location

#### Scenario: Asset without outlet

- **WHEN** a verified admin creates an asset with no outlet
- **THEN** the asset is stored successfully with a null location

### Requirement: Purchase and warranty metadata are optional

Purchase date, purchase cost, currency, warranty end date, and free-text notes MUST be optional. When `purchase_cost` is provided, the system MUST store and expose it as an exact decimal (not a binary float). When both `purchase_date` and `warranty_until` are set, `warranty_until` MUST NOT be before `purchase_date`.

#### Scenario: Cost stored as decimal

- **WHEN** a verified admin sets `purchase_cost` to "45000.00" with currency "BDT"
- **THEN** the system persists and returns the cost without floating-point drift

#### Scenario: Reject warranty before purchase

- **WHEN** a verified admin sets `warranty_until` earlier than `purchase_date`
- **THEN** the system returns a validation error
