## ADDED Requirements

### Requirement: New subscription slots respect meal-off cutoff at creation

When the system creates a new `OrderDelivery` for an active `CustomerSubscription` (subscribe or rolling ensure), it MUST evaluate eligibility using existing meal-off settings for that slot’s `service_date` and `meal_period` in the settings timezone (default `Asia/Dhaka`). The system MUST NOT hardcode lunch or dinner cutoff clock times in application code. Comparison MUST use the same deadline math as customer meal-off: the slot is still eligible while business time is at or before `meal_off_deadline`; after the deadline the slot MUST NOT be created as `scheduled`.

#### Scenario: Subscribe before lunch cutoff keeps lunch scheduled

- **WHEN** lunch off time is `02:00:00` in Asia/Dhaka, menus for the day are published, and a verified customer subscribes to a plan that includes lunch at business time `01:59` on service date `D`
- **THEN** the lunch delivery for `D` is created with status `scheduled`

#### Scenario: Subscribe after lunch cutoff skips lunch

- **WHEN** lunch off time is `02:00:00` in Asia/Dhaka and a verified customer subscribes to a plan that includes lunch at business time `02:01` on service date `D`
- **THEN** the lunch delivery for `D` is created with status `skipped` and is not eligible for auto-delivery charge

#### Scenario: Subscribe after lunch cutoff still schedules dinner when dinner cutoff not passed

- **WHEN** lunch off time is `02:00:00`, dinner off time is `16:00:00`, and a customer on a `both` plan subscribes at `03:00` Asia/Dhaka on date `D`
- **THEN** lunch for `D` is `skipped` and dinner for `D` is `scheduled`

#### Scenario: Subscribe after dinner cutoff skips dinner

- **WHEN** dinner off time is `16:00:00` Asia/Dhaka and a customer subscribes to a plan that includes dinner at business time `16:01` on service date `D`
- **THEN** the dinner delivery for `D` is created with status `skipped`

#### Scenario: Subscribe after both cutoffs skips lunch and dinner

- **WHEN** lunch and dinner cutoffs for `D` have both passed and a customer subscribes to a `both` plan on `D`
- **THEN** both lunch and dinner deliveries for `D` are created as `skipped`

#### Scenario: Subscribe before dinner cutoff keeps dinner scheduled

- **WHEN** dinner off time is `16:00:00` and a customer subscribes at business time `15:59` on service date `D` to a plan that includes dinner
- **THEN** the dinner delivery for `D` is created with status `scheduled`

### Requirement: Cutoff-skipped slots are auditable system skips

When a new subscription delivery is created past its meal-off cutoff, the system MUST persist the row (not omit it), set `status=skipped`, set `skip_source=system`, and record a stable machine-readable reason token `cutoff_passed` in `note` (exact token or a note that contains that token as the documented reason). Customer meal-on MUST remain unavailable for these rows because they are not customer-initiated skips. The system MUST NOT debit the wallet for such slots while they remain `skipped`.

#### Scenario: Cutoff skip is visible for support

- **WHEN** a lunch slot is created after the lunch cutoff during subscribe
- **THEN** the delivery exists with `status=skipped`, `skip_source=system`, and note reason `cutoff_passed`

#### Scenario: Cutoff skip is not charged

- **WHEN** auto-delivery or mark-delivered runs for that meal period and only `scheduled` slots are charged
- **THEN** the cutoff-skipped delivery is not transitioned to `delivered` by auto-delivery and no meal-payment debit is created for it

### Requirement: Existing deliveries and delivery cron are not rewritten by cutoff eligibility

Cutoff eligibility MUST apply only when creating new delivery rows. The system MUST NOT bulk-update existing `scheduled` deliveries to `skipped` as part of this behavior. Auto-delivery eligibility rules that select `status=scheduled` MUST remain unchanged; correctness for new subscribers comes from not creating post-cutoff slots as `scheduled`.

#### Scenario: Ensure does not mutate an existing scheduled row

- **WHEN** a delivery for `(D, lunch)` already exists as `scheduled` and ensure runs again after the lunch cutoff
- **THEN** that existing row remains `scheduled` (idempotent skip of create); no duplicate row is created

#### Scenario: Future dates remain scheduled at subscribe

- **WHEN** a customer subscribes after today’s lunch cutoff and tomorrow’s lunch cutoff has not passed
- **THEN** tomorrow’s lunch delivery is created as `scheduled`

### Requirement: Deadline comparison uses meal-off settings timezone

Cutoff evaluation MUST convert “now” into the `MealOffSettings.timezone` (IANA, production default `Asia/Dhaka`) and MUST combine the service date with the configured `lunch_off_time` or `dinner_off_time` in that timezone. Server host timezone (for example UTC) MUST NOT change the business outcome when settings timezone is Asia/Dhaka.

#### Scenario: Asia/Dhaka lunch cutoff after UTC midnight

- **WHEN** settings timezone is `Asia/Dhaka`, lunch off time is `02:00:00`, and the absolute instant corresponds to `02:01` in Asia/Dhaka on service date `D`
- **THEN** a newly created lunch slot for `D` is `skipped` even if the application process clock is stored in UTC
