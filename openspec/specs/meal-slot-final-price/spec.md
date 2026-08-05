## Purpose

Compute and snapshot per lunch/dinner slot final selling prices from the one-meal cost formula, and use those snapshots as the authoritative wallet charge for delivered meals.

## Requirements

### Requirement: Per-slot final meal selling price uses one-meal cost formula

The system SHALL compute each lunch or dinner menu slot’s final selling price using decimal money arithmetic as:

```text
ingredient_cost = sum of combined unit cost per customer for each ingredient assigned to the slot
operational_cost = per_meal_operational_cost for the schedule’s cycle year and month
profit = ingredient_cost × plan.profit_percent / 100
final_meal_price = ingredient_cost + operational_cost + profit
```

The system MUST use the same unit-cost resolution rules as admin one-meal cost preview (additive kg-derived + flat per-customer costs). The system MUST NOT use package `per_meal_rate` or `Order.per_meal_price_snapshot` as this slot’s final selling price.

#### Scenario: Lunch slot priced from its ingredients

- **WHEN** a lunch slot is assigned Chicken, Rice, and Dal whose combined ingredient cost is `31.00`, month `per_meal_operational_cost` is `25.00`, and plan `profit_percent` is `10`
- **THEN** the slot final meal price equals `31.00 + 25.00 + 3.10 = 59.10` (quantized to project money precision), not the package average meal rate

#### Scenario: Dinner slot can differ from lunch on the same day

- **WHEN** the same day’s dinner slot has a lower ingredient cost than lunch under the same operational cost and profit percent
- **THEN** the dinner `final_meal_price` is lower than the lunch `final_meal_price` for that day

### Requirement: Slot final prices are snapshotted at menu publish

When a verified admin successfully publishes a monthly menu schedule, the system MUST compute and persist immutable snapshot fields on every assigned slot for at least: `final_meal_price`, ingredient cost, operational cost, and profit used in that calculation. Draft (unpublished) schedules MAY omit or recompute live previews without locking snapshots. The system MUST reject publish if any assigned slot cannot resolve ingredient or operational costs required for the formula.

#### Scenario: Publish locks slot prices

- **WHEN** a verified admin publishes a complete monthly menu schedule
- **THEN** each assigned lunch and dinner slot stores a non-null `final_meal_price` snapshot equal to the one-meal formula at publish time

#### Scenario: Publish blocked when an ingredient is unpriced

- **WHEN** a slot includes an ingredient with no resolvable unit cost and the admin publishes
- **THEN** the system rejects publish with a validation error and does not mark the schedule published

### Requirement: Published slot prices are immutable to ingredient catalog changes

While a monthly menu schedule remains published, the system MUST NOT alter stored slot price snapshots when ingredient unit prices are updated, ingredient metadata changes, or an ingredient delete is attempted. Later catalog price changes MUST affect only live draft previews and prices written on a subsequent explicit unpublish → edit → republish of that same schedule.

#### Scenario: Ingredient price rise does not change published July lunch

- **WHEN** a July package menu is published with lunch final price `65.00`, and afterward Chicken’s catalog cost increases
- **THEN** that July lunch slot’s stored final price remains `65.00`

#### Scenario: Ingredient delete does not rewrite published prices

- **WHEN** a published schedule references an ingredient and an admin attempts to delete that ingredient from the catalog
- **THEN** the delete is blocked or otherwise prevented from cascading into published slot rows, and stored slot final prices remain unchanged

### Requirement: Delivery wallet charge uses the published slot final price

When charging a customer wallet for a delivery marked `delivered`, the system MUST debit the `final_meal_price` snapshot of the published menu slot matching the order’s meal package and the delivery’s `service_date` and `meal_period`. The system MUST NOT debit the order’s average `per_meal_price_snapshot` when a slot final price snapshot is available. The system MUST reject the mark-delivered charge path when the matching published slot or its final price snapshot is missing.

#### Scenario: Delivered lunch charges 62 not package average 50

- **WHEN** the package average per-meal rate is `50.00` but the published lunch slot for that delivery’s date has `final_meal_price` `62.00`, and the wallet has sufficient balance
- **THEN** the wallet is debited `62.00` for that delivery

#### Scenario: Delivered dinner charges its own slot price

- **WHEN** the same day’s dinner slot snapshot is `38.00` and that dinner delivery is marked delivered with sufficient balance
- **THEN** the wallet is debited `38.00`, not the lunch price and not the package average

#### Scenario: Missing slot price blocks charge

- **WHEN** an operator marks a delivery delivered but no published slot final price exists for that package, date, and meal period
- **THEN** the system rejects the charge, does not complete a meal-payment debit, and does not leave the delivery successfully charged
