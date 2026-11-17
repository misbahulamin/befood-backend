# Spec Delta

## Purpose

Test Meal orders participate in kitchen, delivery ops, and consolidated meals-served reporting as a distinct third category alongside subscription meals and Guest Meals, without double-counting or changing wallet charge semantics.

## ADDED Requirements

### Requirement: Distinct meal categories in ops

Ops and reporting surfaces that include Test Meals MUST distinguish Subscription Meal, Guest Meal, and Test Meal categories. Test Meal units MUST NOT be mistaken for subscription deliveries or Guest Meal boxes. Guest Meal prepaid wallet debit and subscription delivery charge paths MUST remain unchanged by Test Meal introduction.

#### Scenario: Board exposes separate Test Meal quantity

- **WHEN** a delivery board or today-ops summary includes a stop or zone with Test Meal orders for a slot
- **THEN** Test Meal quantity is exposed separately from regular/subscription and guest quantities

#### Scenario: Guest Meal charge path unchanged

- **WHEN** an active subscriber creates a Guest Meal after Test Meal APIs ship
- **THEN** Guest Meal still debits wallet under existing guest meal rules

### Requirement: Consolidated delivered meals formula

Where a report’s purpose is to count all delivered meal units, the system MUST use an explicit formula: delivered subscription meals + delivered Guest Meals + delivered Test Meals. Reports whose semantics are subscription-only or profit-ledger-specific MUST NOT silently change meaning without documented additive fields.

#### Scenario: Admin meals-served includes Test Meals additively

- **WHEN** delivered subscription count is `100`, delivered guest boxes `5`, and delivered Test Meals `2`
- **THEN** consolidated total delivered meals is `107` when that report is the all-units total

#### Scenario: Profit semantics not silently rewritten

- **WHEN** Test Meal is delivered unpaid
- **THEN** existing guest/subscription profit recognition rules are not redefined as wallet revenue for that Test Meal

### Requirement: Test Meal delivery stop for fulfillment

Each confirmed Test Meal order MUST create or link a fulfillment stop usable by deliveryman/ops for the selected date and meal period, carrying address snapshot and package identity, without requiring an active subscription parent. Marking that stop delivered MUST update the Test Meal order delivered state. Cancelled Test Meals MUST not remain as active cooking/delivery demand.

#### Scenario: Confirmed order appears for rider/ops on service date

- **WHEN** a Test Meal is confirmed for tomorrow lunch in a serviceable zone
- **THEN** ops/rider surfaces for that date and lunch can see the stop with address snapshot

#### Scenario: Deliver updates Test Meal status

- **WHEN** authorized ops mark the Test Meal fulfillment stop delivered
- **THEN** the Test Meal order reflects delivered and delivered timestamp is set

#### Scenario: Cancelled excluded from cooking demand

- **WHEN** a Test Meal order is cancelled before delivery
- **THEN** it does not contribute to final cooking demand for that slot
