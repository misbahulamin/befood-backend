# Spec Delta

## Purpose

Defines additive rider today-board and today-summary meal box quantities so BeFood Express can show regular, guest, and combined totals without double-counting or breaking existing clients.

## ADDED Requirements

### Requirement: Board rows expose regular, guest, and total meal quantities

Each rider today-board customer/delivery row MUST include `meal_quantity` as the regular subscription/order meal quantity for that stop, `guest_quantity` as the aggregated countable Guest Meal quantity for that stop, and `total_meal_quantity` equal to `meal_quantity + guest_quantity`. Existing field semantics for `meal_quantity` and `guest_quantity` MUST be preserved; `meal_quantity` MUST NOT already include guest units. Cancelled Guest Meals MUST be excluded from `guest_quantity`.

#### Scenario: Regular plus guest totals

- **WHEN** a scheduled board row has regular `meal_quantity=2` and aggregated guest quantity `3`
- **THEN** the row includes `guest_quantity=3` and `total_meal_quantity=5`

#### Scenario: Regular only

- **WHEN** a scheduled board row has regular `meal_quantity=5` and no countable guest meals
- **THEN** the row includes `guest_quantity=0` and `total_meal_quantity=5`

#### Scenario: Scheduled and delivered boards use the same quantity contract

- **WHEN** a delivery appears on scheduled or delivered board filters with linked countable guest meals
- **THEN** both representations expose `meal_quantity`, `guest_quantity`, and `total_meal_quantity` under the same additive semantics

### Requirement: Today-summary distinguishes regular, guest, and total boxes

Rider today-summary for the active meal window MUST expose regular meal box totals, guest meal box totals, and combined total meal boxes, plus delivered and pending meal box totals that reconcile with the corresponding board scope (same zone, service date, meal period, status filters, and low-balance exclusion). Package breakdown MAY remain package-stop oriented, but overall meal totals MUST include guest boxes without incorrectly attributing guest units as an extra regular package category.

#### Scenario: Summary reconciles with board boxes

- **WHEN** zone-scoped scheduled+delivered stops sum to 100 regular meals and 15 countable guest meals under the active period
- **THEN** today-summary reports regular `100`, guest `15`, and total `115` for that same scope

#### Scenario: Delivered and pending meal boxes

- **WHEN** under the same scope 70 meal boxes are on delivered stops and 45 meal boxes remain on scheduled stops
- **THEN** today-summary reports delivered `70`, pending `45`, and those values sum to the total meal boxes for that scope

### Requirement: Backward-compatible additive rider fields

The system MUST keep existing rider board and summary keys that clients already consume. New quantity fields MUST be additive. The system MUST NOT rename or remove `meal_quantity` or `guest_quantity` as part of this change.

#### Scenario: Existing keys remain

- **WHEN** a rider client that only reads `meal_quantity` and `guest_quantity` loads today-board after this change
- **THEN** those keys remain present with prior semantics and the client can ignore `total_meal_quantity`
