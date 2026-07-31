## ADDED Requirements

### Requirement: Order create requires published menu for selected meal month

The system SHALL reject meal package order creation when no published `MonthlyMenuSchedule` exists for the ordered meal category and the target meal month (`year`/`month` or current month when omitted). The rejection MUST use a clear customer-facing message indicating the month’s menu has not been published yet and that ordering will be possible once it is published. The system MUST NOT create an order when this gate fails.

#### Scenario: Unpublished month rejects create

- **WHEN** a verified customer attempts to create an order for a meal month with no published schedule for that meal
- **THEN** the system rejects the request with a menu-not-published error and creates no order

#### Scenario: Published month allows create subject to other gates

- **WHEN** a verified customer creates an order for a meal month that has a published schedule and passes month-lock and wallet checks
- **THEN** the system creates the order successfully

#### Scenario: Publish gate runs for omitted month (current)

- **WHEN** a verified customer omits `year`/`month` and the current local month has no published schedule for the meal
- **THEN** the system rejects create with the menu-not-published error
