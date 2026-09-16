## Purpose

Admin-managed monthly meal menus bound to finalized cycle plans, with quota-aware slot assignments and customer publication controls.
## Requirements
### Requirement: Monthly menu schedule binds to a finalized cycle plan

The system SHALL allow a verified admin to create exactly one monthly menu schedule per `MealCyclePlan`. Creation MUST require that plan’s status to be `finalized`. The schedule MUST cover the cycle’s calendar month using slots of `(service_date, meal_period)` where `meal_period` is `lunch` or `dinner`.

#### Scenario: Create schedule from finalized plan

- **WHEN** a verified admin creates a monthly menu schedule for a finalized cycle plan
- **THEN** the system creates a draft schedule linked to that plan and exposes empty or editable slots for every calendar day in the cycle month for both lunch and dinner

#### Scenario: Reject schedule for draft plan

- **WHEN** a verified admin attempts to create a monthly menu schedule for a draft cycle plan
- **THEN** the system rejects the request with a validation error

#### Scenario: One schedule per plan

- **WHEN** a verified admin attempts to create a second monthly menu schedule for the same cycle plan
- **THEN** the system rejects the request with a conflict or validation error

### Requirement: Slot assignments respect plan servings quotas

The system SHALL allow verified admins to assign ingredients from the linked cycle plan’s lines onto schedule slots. For each ingredient, the count of slot assignments across the schedule MUST NOT exceed that ingredient’s `servings_count` on the linked `MealCyclePlanLine`. Assignments MUST only use ingredients that exist on the linked plan.

#### Scenario: Chicken quota enforced

- **WHEN** a plan allows Chicken `servings_count = 6` and the admin already scheduled Chicken on 6 slots
- **THEN** scheduling Chicken on a seventh slot is rejected with a validation error identifying remaining quota `0`

#### Scenario: Ingredient not on plan rejected

- **WHEN** an admin tries to assign an ingredient that is not a line on the linked cycle plan
- **THEN** the system rejects the assignment

#### Scenario: Bulk save within quotas succeeds

- **WHEN** a verified admin submits a full-month assignment matrix whose per-ingredient totals are within each plan line’s `servings_count`
- **THEN** the system replaces the schedule assignments atomically and returns updated quota usage

### Requirement: Main protein slot fill and period balance rules

The system SHALL treat each `(service_date, meal_period)` slot as requiring at most one ingredient with `product_role=main`. Publishing a schedule MUST require that every slot in the month has exactly one main assignment, and that the total main assignments equals the cycle’s `total_meals`. The system MUST expose remaining quota and lunch/dinner usage counts per ingredient to help admins balance periods, with recommended remaining splits as even as possible and any odd remainder preferring lunch unless an admin supplies an explicit preference.

#### Scenario: Publish blocked when a slot lacks a main

- **WHEN** any lunch or dinner slot in the month has no `main` ingredient assigned and the admin publishes
- **THEN** the system rejects publish with a validation error listing incomplete slots

#### Scenario: Duplicate main on one slot rejected

- **WHEN** an admin tries to assign two `main` ingredients to the same date and meal period
- **THEN** the system rejects the assignment

#### Scenario: Quota usage shows lunch and dinner split

- **WHEN** an admin requests schedule quota summary after assigning Chicken 8 times to lunch and 4 times to dinner
- **THEN** the response reports Chicken usage `12` with `lunch=8`, `dinner=4`, and remaining based on the plan line

#### Scenario: Odd remaining quota prefers lunch

- **WHEN** an ingredient has `3` unplaced servings left and empty slots exist in both periods
- **THEN** the suggestion places `2` on lunch and `1` on dinner (or documents the configured preference equivalently)

### Requirement: Schedule draft and publish lifecycle for kitchen use

The system SHALL support schedule statuses `draft` and `published`. Only verified admins MAY create, edit, publish, or unpublish schedules. Full-month schedule detail MUST NOT be exposed on public unauthenticated meal APIs except through the dedicated public package menu endpoint, which returns published slot contents only for the requested calendar month matching the linked cycle's `(year, month)`. Publishing a schedule for cycle month M makes that package's menu visible to customers and marketing pages only when clients query year/month M (or when discovery metadata directs them to M). Published schedules are the source of truth for customer today's-menu data for that package and month.

#### Scenario: Draft edits allowed

- **WHEN** a schedule is `draft` and a verified admin updates slot assignments within quotas
- **THEN** the system accepts the update

#### Scenario: Published schedule still admin-readable for kitchen prep

- **WHEN** a verified admin requests the full monthly schedule for a published schedule
- **THEN** the system returns all dates and meal periods with assigned ingredients for kitchen preparation

#### Scenario: Unauthenticated full-month access denied

- **WHEN** an unauthenticated client requests a full monthly menu schedule
- **THEN** the system returns `401` or otherwise denies access

#### Scenario: Customer visibility scoped to published cycle month

- **WHEN** an admin publishes the September 2026 schedule for Student Package
- **THEN** public and customer menu APIs return published slot contents for `year=2026&month=9` and return `schedule_published` false with empty days for `year=2026&month=8` until August is separately published

### Requirement: Side and staple assignments are optional but quota-bound

The system SHALL allow zero or more non-main ingredients (`side`, `staple`, `seasoning`, `other`) on a slot, each still bound by that ingredient’s plan `servings_count`. Publishing MUST NOT require every non-main quota to be fully consumed; remaining non-main quota is allowed.

#### Scenario: Side under-quota publish allowed

- **WHEN** Vegetables has `servings_count = 20` but only 18 slot assignments and all mains are complete
- **THEN** the system allows publish

#### Scenario: Side over-quota rejected

- **WHEN** an admin attempts to assign Vegetables beyond its plan `servings_count`
- **THEN** the system rejects the assignment

### Requirement: Admin schedule detail exposes dual meal pricing

When a verified admin retrieves full monthly menu schedule detail (including published menus used by the admin published-menus page), each assignment slot that includes final-price exposure MUST include additive dual-pricing fields computed on the backend:

- shared cost inputs: selected/ingredient cost and operational cost
- `subscriber_pricing` with `profit_percent`, `profit_amount`, and `final_price`
- `instant_pricing` with `profit_percent`, `profit_amount`, and `final_price` from the latest active Instant meal settings
- flat aliases `subscriber_price` and `instant_price` equal to the respective final prices when priced

Existing `final_meal_price` (subscriber) MUST remain present and unchanged in meaning. Customer-visible and public schedule payloads MUST NOT receive Instant margin internals unless an existing public Instant endpoint already defines those fields.

#### Scenario: Published slot returns subscriber and Instant ladders

- **WHEN** a verified admin retrieves a published schedule whose lunch slot has ingredient cost `48.15`, operational cost `4.13`, subscriber profit percent `14.45`, and Instant settings profit percent `70.00`
- **THEN** the lunch assignment includes ingredient/operational costs, subscriber final price `59.24` with profit `6.96`, Instant final price `85.99` with profit `33.71` (money quantized with half-up), and `final_meal_price` still equals the subscriber final price

#### Scenario: Instant settings change refreshes Instant ladder only

- **WHEN** Instant meal settings `profit_percent` changes from `70` to `80` and the admin refreshes the same published schedule detail without republishing
- **THEN** Instant final price and Instant profit update for the new percent, and subscriber `final_meal_price` / subscriber profit snapshots remain unchanged

#### Scenario: Existing final_meal_price clients keep working

- **WHEN** a client reads only `final_meal_price` from admin schedule assignments after dual-pricing fields are added
- **THEN** the field remains present with the subscriber selling price and no required schema break

### Requirement: Dual pricing uses Instant settings and publish cost basis

For published slots, dual pricing MUST prefer publish-time ingredient and operational cost snapshots when present. Instant `profit_percent` MUST come from `InstantMealSettings` (latest active singleton settings), not from the cycle plan and not from a hardcoded constant. Subscriber pricing MUST continue to reflect plan profit used at publish (snapshots), not Instant settings.

#### Scenario: Instant percent not taken from cycle plan

- **WHEN** the cycle plan profit percent is `14.45` and Instant settings profit percent is `70.00`
- **THEN** `instant_pricing.profit_percent` is `70.00` and `subscriber_pricing.profit_percent` reflects the subscriber/plan value used for that slot

#### Scenario: Missing snapshots do not fabricate zero Instant price

- **WHEN** an admin views a draft or unpriceable slot without resolvable cost snapshots or live costs
- **THEN** Instant and subscriber pricing fields are null or omitted per API contract and MUST NOT return fabricated `0.00` selling prices

### Requirement: Draft schedule auto-reconciles when plan servings decrease

When a linked cycle plan's lines are replaced via servings matrix save and a draft monthly menu schedule exists for that plan, the system SHALL automatically remove excess slot assignments so that per-ingredient usage in the schedule does not exceed each plan line's new `servings_count`. The schedule row and all unaffected assignments MUST be preserved.

#### Scenario: Decrease by one removes one assignment

- **WHEN** a draft schedule assigns ingredient "Egg Curry" on 5 slots and the admin saves a plan matrix reducing Egg Curry `servings_count` from 5 to 4
- **THEN** exactly one Egg Curry slot assignment is removed, four remain, and the schedule is not deleted

#### Scenario: Decrease to zero removes all assignments

- **WHEN** a draft schedule assigns ingredient "Regular Egg Fry" on 1 slot and the admin saves a plan matrix setting that ingredient's `servings_count` to 0 or removing the ingredient from the plan
- **THEN** all Regular Egg Fry slot assignments are removed and quota summary shows `used = 0` and `over_quota = false`

#### Scenario: Increase does not auto-add assignments

- **WHEN** a draft schedule uses Chicken on 10 slots and the admin increases Chicken `servings_count` from 10 to 12
- **THEN** the schedule still has 10 Chicken assignments and remaining quota is 2 for manual assignment

#### Scenario: Save assignments succeeds after reconciliation

- **WHEN** a draft schedule was over quota before plan line save and reconciliation runs as part of the same plan line update
- **THEN** a subsequent assignment save or publish attempt is not blocked solely by the prior over-quota state for trimmed ingredients

#### Scenario: Published schedule not reconciled via plan line edit

- **WHEN** a plan has a published monthly menu schedule
- **THEN** plan line replacement is not allowed while finalized and reconciliation does not mutate published schedules

#### Scenario: Deterministic trim order

- **WHEN** reconciliation must remove N assignments for an ingredient
- **THEN** the system removes assignments from the latest `service_date` first and prefers `dinner` before `lunch` on the same date

