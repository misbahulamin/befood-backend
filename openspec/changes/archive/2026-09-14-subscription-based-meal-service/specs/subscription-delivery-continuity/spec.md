## ADDED Requirements

### Requirement: Active subscriptions generate rolling delivery slots

While a `CustomerSubscription` is `active`, the system SHALL ensure `OrderDelivery` rows exist for each service date from `started_on` through a rolling horizon of **today through the last day of the next calendar month** (meal-off timezone). New slots MUST set `subscription_id` and MUST leave `order_id` null. Slot `meal_period` values MUST follow `meal_period_snapshot` (`lunch` only, `dinner` only, or both). Generation MUST be idempotent: existing slots MUST NOT be duplicated.

#### Scenario: Subscribe generates current and next month when menus published

- **WHEN** a customer subscribes on 18 August 2026 to a `both` plan and published menus exist for August and September
- **THEN** the system creates lunch and dinner slots for each remaining in-horizon day from `started_on` through 30 September without a monthly `Order`

#### Scenario: Ensure is idempotent

- **WHEN** `ensure_subscription_deliveries` runs twice for the same active subscription and horizon
- **THEN** no duplicate `(subscription, service_date, meal_period)` rows exist

#### Scenario: Cancelled subscription does not generate further slots

- **WHEN** a subscription is `cancelled` and the ensure job runs
- **THEN** the system MUST NOT create new scheduled slots after `cancel_effective_on`

### Requirement: Unpublished months skip slot generation without cancelling the subscription

The system MUST create slots for a calendar month only when a published `MonthlyMenuSchedule` exists for that subscription’s meal package and month. If the menu is unpublished, the system MUST skip those dates, MUST leave the subscription `active`, and MUST generate those slots later when a published schedule exists and ensure runs again. Subscribe MUST NOT be rejected solely because a future month in the horizon is unpublished.

#### Scenario: Subscribe succeeds without next month published

- **WHEN** August menu is published, September is not, and a customer subscribes in August
- **THEN** the subscription is created `active` and September dates have no slots yet

#### Scenario: Slots appear after later publish

- **WHEN** September’s menu is published and ensure runs for an active August subscriber
- **THEN** September lunch/dinner slots exist according to `meal_period_snapshot`

### Requirement: Subscription does not complete when a month’s slots are terminal

The system MUST NOT transition an `active` subscription to `cancelled` or any completed status because all slots in a calendar month are `delivered`, `skipped`, or `missed`. Service continues into the next horizon until the customer (or admin) cancels.

#### Scenario: End of month does not end subscription

- **WHEN** every August slot for an active subscription is terminal and the local date is 1 September
- **THEN** the subscription remains `active` and September slots are generated when the month is published
