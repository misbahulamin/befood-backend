# Spec Delta

## Purpose

Make Admin Guest Meals summary metrics financially unambiguous by distinguishing prepaid order value from delivered recognized revenue and related box counts.

## ADDED Requirements

### Requirement: Prepaid order value is distinct from recognized revenue
The Admin Guest Meals list summary MUST expose the filtered sum of Guest Meal order `total_amount` as prepaid/order value, not as delivered realized revenue. The system MUST also expose delivered recognized Guest Meal revenue for delivered quantities/orders in the same filter scope when realization data is available.

#### Scenario: Mixed scheduled and delivered orders
- **WHEN** filtered Guest Meal orders include scheduled prepaid value `435.50` and a delivered order value `140.00`
- **THEN** prepaid/order value totals `575.50` while delivered recognized guest revenue totals `140.00` (not `575.50`)

### Requirement: Box quantity metrics stay status-aware
The summary MUST continue to report order count, total ordered box quantity, scheduled box quantity, delivered box quantity, and cancelled box quantity using Guest Meal status filters. Delivered box quantity MUST sum `quantity` for delivered orders only.

#### Scenario: Delivered boxes use quantity not row count
- **WHEN** one delivered Guest Meal order has quantity `2`
- **THEN** delivered box quantity includes `2`

### Requirement: Labels and fields remain machine-clear
API field names or documented aliases MUST make prepaid order value vs delivered recognized revenue distinguishable for clients. Existing clients that read the legacy `revenue` key MUST either keep receiving prepaid order value with additive recognized-revenue fields, or receive an additive rename path without a silent semantic flip that breaks screens.

#### Scenario: Additive recognized revenue field
- **WHEN** an admin client requests the Guest Meals summary after this change
- **THEN** it can display prepaid order value and delivered recognized revenue as separate figures without client-side ledger reconstruction
