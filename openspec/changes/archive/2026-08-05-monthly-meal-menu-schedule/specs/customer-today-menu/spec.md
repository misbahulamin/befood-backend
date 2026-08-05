## ADDED Requirements

### Requirement: Customer today menu requires auth and active purchase

The system SHALL provide a customer today’s-menu API that requires authentication as a verified customer (or equivalent logged-in customer). The system MUST return menu data only for `MealCategory` packages for which the customer has an active order covering today’s business-local date (`order_start_date ≤ today ≤ order_end_date` and order not cancelled). Customers MUST NOT receive full-month schedules through this API.

#### Scenario: Active order sees today menu for that package

- **WHEN** a logged-in customer has a non-cancelled order for Regular Package covering today and that package has a published schedule for the current month
- **THEN** the API returns today’s visible meal period(s) for Regular Package only

#### Scenario: No active order

- **WHEN** a logged-in customer has no order covering today
- **THEN** the API returns an empty result set or a clear not-eligible response without exposing other packages’ menus

#### Scenario: Unauthenticated denied

- **WHEN** an unauthenticated client calls the today-menu API
- **THEN** the system returns `401`

### Requirement: Today menu respects reveal windows and published schedule

The system MUST include a meal period in the today-menu response only when (1) the linked monthly schedule for that package’s current month is `published`, (2) the period’s reveal time has been reached for the business-local “today”, and (3) the slot has assignments. If the schedule is missing or not published, the system MUST NOT invent menu items from cycle plan servings alone.

#### Scenario: Lunch visible after reveal

- **WHEN** it is after lunch reveal and before dinner reveal, and lunch slot assignments exist on the published schedule
- **THEN** the response includes today’s lunch ingredients and excludes dinner

#### Scenario: Dinner appears after dinner reveal

- **WHEN** it is after dinner reveal and dinner slot assignments exist
- **THEN** the response includes today’s dinner ingredients

#### Scenario: Unpublished schedule hidden from customer

- **WHEN** the package schedule for the month is still `draft`
- **THEN** the customer today-menu API does not return that package’s slot ingredients

### Requirement: Response is package-scoped and lean

The today-menu response MUST identify the meal package (`meal_category` id and display name), the service date, each visible `meal_period`, and the assigned ingredients (id, name, and product_role at minimum). The payload MUST remain suitable for mobile clients (flat, minimal nesting).

#### Scenario: Lean today payload

- **WHEN** a customer with an active Regular Package order requests today’s menu after both reveal times
- **THEN** the response includes package identity, date, lunch and dinner ingredient lists without unrelated order or costing fields
