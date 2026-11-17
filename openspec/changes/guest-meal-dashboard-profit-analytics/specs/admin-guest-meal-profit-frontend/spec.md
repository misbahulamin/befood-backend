# Spec Delta

## Purpose

Define Admin UI behavior for Dashboard, Profit, and Guest Meals pages so displayed meals-served and financial totals match backend guest-aware aggregates without inventing client-side accounting.

## ADDED Requirements

### Requirement: Dashboard meals served uses backend totals including guest boxes
The Admin Dashboard meals-served cards MUST display backend total food boxes that include delivered Guest Meal quantities. Optional compact regular/guest breakdown MAY be shown without cluttering the existing card layout. Catalog menu-item counts MUST remain unchanged.

#### Scenario: Total meals served reflects guest contribution
- **WHEN** backend lifetime regular served is `66` and guest served is `2`
- **THEN** the Dashboard Total Meals Served card shows `68` (or an equivalent backend-provided total) rather than `66`

### Requirement: Today Delivery card keeps stop semantics
If the existing Today’s Delivery card is bound to delivery-stop count, the UI MUST preserve that meaning. Food-box counts for today, if shown, MUST appear as a separate secondary metric rather than silently replacing the stop count.

#### Scenario: Stop card not inflated by guest boxes
- **WHEN** today has one delivered stop with two guest boxes
- **THEN** the Today’s Delivery stop metric remains `1`

### Requirement: Profit page uses backend guest-inclusive aggregates
Admin Profit overview cards, range revenue/cost/profit, daily chart, and history MUST consume backend responses that already include realized Guest Meal contributions. The UI MUST NOT recompute chart or range profit with a separate frontend formula that omits guest realization.

#### Scenario: Range revenue includes delivered guest revenue
- **WHEN** backend range regular revenue is `33.55` and delivered guest revenue is `140.00`
- **THEN** the Profit range revenue display equals the backend total `173.55` (subject to formatting)

#### Scenario: History can identify guest realization
- **WHEN** a Guest Meal realization exists in the filtered history window
- **THEN** Profit History shows enough fields to identify date, customer, meal type/source, quantity or amount, revenue, cost, and profit for that entry

### Requirement: Guest Meals page labels prepaid vs realized figures
The Admin Guest Meals page MUST label prepaid order value separately from delivered recognized revenue when both are available from the API. Scheduled boxes MUST NOT be presented as served or as realized revenue.

#### Scenario: Revenue card is not misread as realized
- **WHEN** the Guest Meals summary includes prepaid order value `575.50` and delivered recognized revenue `140.00`
- **THEN** the page presents those as distinct metrics with unambiguous labels
