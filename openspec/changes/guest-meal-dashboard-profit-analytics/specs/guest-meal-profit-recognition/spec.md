# Spec Delta

## Purpose

Recognize realized Guest Meal revenue, attributable cost, and profit when prepaid guest boxes are actually delivered, without a second customer wallet debit and without duplicate ledger entries.

## ADDED Requirements

### Requirement: Guest Meal realization happens on successful parent delivery
When linked Guest Meal orders transition to delivered with their parent subscription delivery stop, the system SHALL recognize realized Guest Meal financials for reporting. Recognition MUST NOT debit the customer wallet again for those prepaid guest amounts.

#### Scenario: Delivered guest boxes are recognized once
- **WHEN** a parent delivery is marked delivered and a linked Guest Meal order with quantity `2` and prepaid `total_amount` `140.00` becomes delivered
- **THEN** realized Guest Meal revenue for that order is recognized exactly once and the customer wallet is not debited again for the guest amount

#### Scenario: Scheduled guest boxes are not realized
- **WHEN** a Guest Meal order remains `scheduled` (parent not delivered)
- **THEN** the system does not recognize that order’s prepaid amount as delivered-meal revenue or profit

### Requirement: Guest revenue uses prepaid snapshots at realization
Recognized Guest Meal revenue MUST equal the delivered order’s snapshotted `total_amount`, or equivalently delivered quantity × snapshotted `unit_price`, using purchase-time price snapshots. Revenue MUST be attributed to the Guest Meal `service_date` and `meal_period`, not the purchase `created_at`.

#### Scenario: Purchase date differs from service date
- **WHEN** a Guest Meal is purchased on date A for service date B and later delivered on B
- **THEN** realized Guest Meal revenue is reported against service date B

### Requirement: Guest attributable cost uses published slot snapshots times quantity
Attributable Guest Meal food cost MUST use the published menu slot `ingredient_cost_snapshot` for the linked package, service date, and meal period, multiplied by delivered guest quantity. Operational cost MUST use the published slot `operational_cost_snapshot` × quantity when present. The Guest Meal `box_price` selling component MUST NOT be treated as packaging cost. Missing snapshots MUST contribute `0.00` for that cost component without inventing live catalog costs.

#### Scenario: Two guest boxes use slot cost times quantity
- **WHEN** a delivered Guest Meal has quantity `2` and the published slot ingredient cost snapshot is `30.50`
- **THEN** recognized guest food cost is `61.00` (subject to money quantization)

#### Scenario: Box selling price is not recorded as cost
- **WHEN** a delivered Guest Meal has a non-zero snapshotted `box_price`
- **THEN** that `box_price` is not added into food cost or operational cost solely because it is a selling-price component

### Requirement: Guest profit equals recognized revenue minus attributable costs
Realized Guest Meal profit MUST equal recognized Guest Meal revenue minus attributable food cost minus attributable operational cost, using Decimal money precision. The system MUST NOT display an invented profit when required snapshot inputs are missing; missing cost snapshots contribute `0.00` and profit remains auditable from stored components.

#### Scenario: Profit reconciles from stored components
- **WHEN** recognized guest revenue is `140.00`, food cost is `61.00`, and operational cost is `0.00`
- **THEN** realized guest profit equals `79.00`

### Requirement: Guest Meal financial recognition is idempotent
Each delivered Guest Meal order MUST produce at most one realized profit recognition record. Retries of mark-delivered, concurrent sync attempts, and reconciliation runs MUST NOT create duplicate guest revenue, cost, or profit.

#### Scenario: Duplicate mark-delivered does not double-count guest profit
- **WHEN** mark-delivered is processed twice for the same parent delivery that already recognized a linked Guest Meal order
- **THEN** still exactly one guest realization record exists for that Guest Meal order and aggregates are unchanged by the retry

#### Scenario: Concurrent recognition creates a single guest row
- **WHEN** two concurrent recognition attempts target the same newly delivered Guest Meal order
- **THEN** exactly one guest realization record is persisted

### Requirement: Historical delivered Guest Meals can be reconciled safely
The system SHALL provide an auditable reconciliation path that finds delivered Guest Meal orders missing realization records and can create missing rows idempotently. Default operation MUST support dry-run discrepancy reporting. Destructive or production-wide backfill MUST NOT run without explicit operator approval flags.

#### Scenario: Dry-run lists missing guest realizations
- **WHEN** an operator runs guest-meal profit reconciliation in dry-run mode and a delivered Guest Meal lacks a realization record
- **THEN** the command reports that discrepancy without writing ledger rows

#### Scenario: Apply mode is idempotent
- **WHEN** reconciliation apply mode is run twice for the same missing delivered Guest Meal
- **THEN** exactly one realization record exists afterward
