## Purpose

Expose Instant Meal display cards derived from published monthly package menu slots for non-subscriber browsing, without Instant order placement and without changing subscription meal pricing.

## ADDED Requirements

### Requirement: Instant Meals are projections of published menu slots

The system SHALL treat each Instant Meal as a read-only projection of one published `MonthlyMenuSlot` (package schedule × `service_date` × `meal_period`). The system MUST NOT create a separate persisted Instant Meal catalog table for this capability. The system MUST include only slots whose parent monthly menu schedule is published and that have assigned ingredients. Draft or unpublished schedules MUST NOT appear as Instant Meals.

#### Scenario: Published lunch becomes an Instant Meal card

- **WHEN** Student Package has a published September schedule with Day 1 lunch ingredients assigned
- **THEN** that lunch slot is eligible to appear as one Instant Meal object for that date and package

#### Scenario: Same day lunch and dinner are separate Instant Meals

- **WHEN** a package’s published schedule has both lunch and dinner on 1 September
- **THEN** the Instant Meal list includes two distinct Instant Meal objects for that package and date (one lunch, one dinner)

#### Scenario: Unpublished schedule is excluded

- **WHEN** a package schedule for a month remains draft
- **THEN** none of that schedule’s slots appear in the Instant Meal list

### Requirement: Instant Meal date window follows admin duration and excludes past dates

The system SHALL include Instant Meals only for local business calendar dates in the inclusive window starting at today’s local date and spanning `duration_days` days from Instant Meal settings (`end_date = today + duration_days - 1`). The system MUST exclude any slot with `service_date` before today. The system MUST NOT accept free-form admin date ranges for this window (duration is configured only via Instant Meal admin settings).

#### Scenario: Seven-day window from today

- **WHEN** today is 28 August and Instant Meal `duration_days` is `7`
- **THEN** Instant Meals are limited to service dates from 28 August through 3 September inclusive (when published slots exist)

#### Scenario: Today-only window

- **WHEN** Instant Meal `duration_days` is `1`
- **THEN** only Instant Meals with `service_date` equal to today are returned

#### Scenario: Past dates hidden

- **WHEN** a published slot exists for yesterday
- **THEN** that slot is not returned in the Instant Meal list

### Requirement: Instant Meal price uses Instant profit, not subscription plan profit

The system SHALL compute each Instant Meal `price` using decimal money arithmetic as:

```text
ingredient_cost = published slot ingredient cost snapshot when present,
                  otherwise the sum of combined unit cost per customer for slot ingredients
operational_cost = per-meal operational cost for the slot’s service year and month
                   (same resolution rules as operational cost services)
profit = ingredient_cost × InstantMealSettings.profit_percent / 100
price = ingredient_cost + operational_cost + profit
```

The system MUST use Instant Meal settings `profit_percent` and MUST NOT use `MealCyclePlan.profit_percent` for Instant price. The system MUST NOT write Instant prices into subscription slot snapshot fields and MUST NOT change package finalize or menu publish pricing logic.

#### Scenario: Default fifty percent Instant margin on ingredient cost

- **WHEN** ingredient cost is `40.00`, operational cost is `0` for the example month configuration used in the test, and Instant `profit_percent` is `50`
- **THEN** Instant `price` equals `60.00` (quantized to project money precision)

#### Scenario: Ingredient plus operational plus Instant profit

- **WHEN** ingredient cost is `40.00`, month per-meal operational cost is `10.00`, and Instant `profit_percent` is `70`
- **THEN** Instant `price` equals `40.00 + 10.00 + 28.00 = 78.00`

#### Scenario: Subscription slot snapshot unchanged after Instant settings change

- **WHEN** a verified admin changes Instant `profit_percent` from `50` to `70`
- **THEN** existing published slot `final_meal_price_snapshot` and related subscription snapshots remain unchanged

### Requirement: Instant Meal list API returns ordered display cards

The system SHALL provide a public Instant Meal list API that returns Instant Meal objects with at least: stable `public_id`, display `name`, `meal_period` (`lunch`|`dinner`), `service_date`, package identity (`package_public_id`, `package_name`), Instant `price`, `ingredient_cost`, optional `image`, and `subscriber_price` when the published slot final price snapshot is available. The system MUST order results by ascending `service_date`, then `lunch` before `dinner`, then a stable package tie-breaker. The system MUST NOT return marketing copy strings for subscription upsell; frontend owns static messaging using `subscriber_price`.

#### Scenario: Oldest upcoming date first

- **WHEN** Instant Meals exist for 1 Sep, 2 Sep, and 3 Sep within the window
- **THEN** the API returns them in date order 1 Sep, then 2 Sep, then 3 Sep

#### Scenario: Subscriber price value without marketing text

- **WHEN** Instant `price` is `80.00` and the published slot `final_meal_price_snapshot` is `52.00`
- **THEN** the Instant Meal object includes `subscriber_price` = `52.00` and does not require a backend `subscription_message` string

#### Scenario: Multiple packages produce separate cards for the same date and period

- **WHEN** Student and Regular both have published lunch on the same date within the window
- **THEN** the API returns two Instant Meal objects (one per package) for that date and lunch period

### Requirement: Instant Meal capability does not break subscription flows

The system MUST keep existing subscription package menus, publish/unpublish, slot final price snapshots, and subscriber wallet debit behavior unchanged when Instant Meal APIs and settings are introduced.

#### Scenario: Existing published menu APIs still work after Instant Meal ships

- **WHEN** Instant Meal list and settings endpoints are deployed
- **THEN** existing public package menu, today menu, and delivery charge paths continue to use subscription pricing rules as before
