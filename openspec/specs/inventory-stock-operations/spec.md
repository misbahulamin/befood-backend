## Purpose

Kitchen stock operations for verified admins: usage/issue, wastage, and adjustments with negative-stock guards, plus paginated usage history and complete item movement history.

## Requirements

### Requirement: Verified admin can issue kitchen stock usage
The system SHALL allow verified admins to create kitchen usage (stock issue) entries that debit inventory for cooking. Each entry MUST include inventory item, quantity used, unit (converted to item default when allowed), optional purpose, optional meal/menu reference, optional kitchen batch, optional note, issued-by admin, and timestamps. Successful issue MUST create a kitchen usage stock movement and reduce on-hand quantity atomically with negative-stock guards.

#### Scenario: Issue stock for kitchen use
- **WHEN** Beef on-hand is `55` kg and a verified admin issues `12` kg for kitchen use with a purpose
- **THEN** on-hand becomes `43` kg and a kitchen usage history row records item, quantity, purpose, issuer, and remaining stock

#### Scenario: Issue above available stock fails
- **WHEN** available stock is `10` kg and an admin issues `15` kg
- **THEN** the system rejects the issue with an insufficient stock error and does not change on-hand

### Requirement: Verified admin can record wastage
The system SHALL allow verified admins to record wastage that reduces on-hand quantity via a wastage stock movement, subject to the same negative-stock guard. Wastage entries MUST record item, quantity, unit, reason/note, acting admin, and timestamps.

#### Scenario: Record wastage within available stock
- **WHEN** Onion on-hand is `20` kg and an admin records `3` kg wastage with a reason
- **THEN** on-hand becomes `17` kg and a wastage movement of `-3` exists

### Requirement: Verified admin can adjust stock
The system SHALL allow verified admins to post stock adjustments with a signed quantity delta (increase or decrease), reason, acting admin, and timestamps. Negative adjustments MUST enforce the negative-stock guard. Positive adjustments MUST increase on-hand via an adjustment movement. Adjustment MUST be audited.

#### Scenario: Positive adjustment increases stock
- **WHEN** Rice on-hand is `100` kg and an admin posts a `+2` kg adjustment with reason `Count correction`
- **THEN** on-hand becomes `102` kg and an adjustment movement of `+2` exists

#### Scenario: Negative adjustment blocked below zero
- **WHEN** Salt on-hand is `1` kg and an admin posts a `-5` kg adjustment
- **THEN** the system rejects the adjustment and leaves on-hand unchanged

### Requirement: Stock usage history
The system SHALL provide a paginated kitchen usage history for verified admins including date/time, item, quantity used, purpose, kitchen/menu reference when present, issued-by admin, and remaining stock after the movement. Filters MUST be allowlisted (at least date range, item, and admin). Unsupported filters MUST return `400`.

#### Scenario: List usage history for an item
- **WHEN** a verified admin requests usage history filtered by Beef
- **THEN** only Beef kitchen usage rows are returned in deterministic order

### Requirement: Item complete movement history
The system SHALL expose a complete movement history for an inventory item including purchases, kitchen usages, wastages, adjustments, and reversals with signed quantities, type labels, acting admin, and timestamps so admins can reconstruct how stock changed.

#### Scenario: Item detail shows mixed history
- **WHEN** Beef has purchase `+50`, usage `-10`, usage `-5`, and purchase `+20` movements
- **THEN** item history returns those movements in deterministic order with types and actors
