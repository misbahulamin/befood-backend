## ADDED Requirements

### Requirement: Verified admin can manage inventory item master
The system SHALL allow verified admins to create, list, retrieve, and update stockable inventory items used for kitchen stock (not meal costing catalog products). Each item MUST include a unique name, default unit from the allowlisted unit set, optional category, admin lifecycle status (`active` | `inactive`), optional minimum stock level in the default unit, created-by admin reference, and created/updated timestamps. Item identity exposed to clients MUST use `public_id`. Free-text duplicate names MUST be rejected (case-insensitive uniqueness).

#### Scenario: Create inventory item
- **WHEN** a verified admin creates an item named `Beef` with default unit `kg` and category `meat`
- **THEN** the system stores the item with zero on-hand quantity and returns its `public_id`, name, default unit, category, and status

#### Scenario: Reject duplicate item name
- **WHEN** a verified admin attempts to create an item whose name matches an existing inventory item ignoring case
- **THEN** the system rejects the request and does not create a second item

#### Scenario: Non-admin denied item write
- **WHEN** a customer or unauthenticated client calls inventory item write endpoints
- **THEN** the system denies access with `401` or `403`

### Requirement: Supported inventory units
The system SHALL support the allowlisted units `kg`, `g`, `l`, `ml`, `piece`, `packet`, `box`, `bottle`, and `bag`. Each inventory item MUST have exactly one default unit from that allowlist. Requests that set an unsupported unit MUST be rejected.

#### Scenario: Reject unsupported unit
- **WHEN** a verified admin creates or updates an item with unit `ton`
- **THEN** the system returns a validation error and does not persist the unsupported unit

### Requirement: Low stock and out of stock signals
The system SHALL expose read-only stock signals for each item derived from on-hand quantity and optional minimum stock level: `out_of_stock` when on-hand is less than or equal to zero; `low_stock` when a minimum is set, on-hand is greater than zero, and on-hand is less than or equal to the minimum. Inactive admin status MUST NOT by itself clear historical stock data.

#### Scenario: Low stock when below minimum
- **WHEN** Beef has minimum stock `10` kg and on-hand quantity is `8` kg
- **THEN** item detail/list marks the item as `low_stock` and not `out_of_stock`

#### Scenario: Out of stock at zero
- **WHEN** an item’s on-hand quantity is `0`
- **THEN** the item is marked `out_of_stock`

### Requirement: Optional link to meal costing ingredient
The system MAY allow an optional link from an inventory item to an existing meal costing `Ingredient` for future mapping. Inventory item master MUST remain usable when no costing ingredient link is set. Inventory APIs MUST NOT require meal catalog fields such as `price_per_kg` or `cost_per_customer`.

#### Scenario: Create item without costing ingredient
- **WHEN** a verified admin creates an inventory item without a linked meal ingredient
- **THEN** the system accepts the item and treats it as a standalone stock SKU
