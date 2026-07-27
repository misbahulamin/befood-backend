## ADDED Requirements

### Requirement: Customer sets lunch and dinner default delivery places
The system SHALL store at most one default delivery place for lunch and at most one for dinner per customer. The same place MAY be selected for both periods. Preference updates MUST accept place identity via `public_id` and MUST verify ownership. Clearing a period’s default MUST be explicit and documented. Unauthenticated access MUST be rejected.

#### Scenario: Set distinct lunch and dinner places
- **WHEN** an authenticated customer sets lunch to place A and dinner to place B (both owned)
- **THEN** the system persists both preferences and subsequent reads return those `public_id` values

#### Scenario: Same place for both periods
- **WHEN** an authenticated customer sets both lunch and dinner to the same owned place
- **THEN** the system accepts the configuration

#### Scenario: Foreign place rejected
- **WHEN** an authenticated customer attempts to set a preference to another customer’s place `public_id`
- **THEN** the system responds `404` or `422` and does not store the foreign place

### Requirement: Customer can set weekday overrides per meal period
The system SHALL allow weekday overrides that map `(meal_period, weekday)` to an owned delivery place. Weekday MUST use a documented `0–6` Monday-first convention in the API. At most one override MUST exist per customer + meal period + weekday. Overrides MUST NOT be required for basic use; defaults alone MUST be sufficient.

#### Scenario: Weekday lunch override
- **WHEN** an authenticated customer sets Monday–Friday lunch overrides to Office and leaves dinner on the Home default
- **THEN** resolution for a Monday lunch uses Office while Monday dinner still uses Home

#### Scenario: Replace override set
- **WHEN** an authenticated customer submits an updated override list for their preferences
- **THEN** the system stores the new set as the source of truth for that customer’s overrides (documented put/replace or upsert semantics)

#### Scenario: Override with foreign place rejected
- **WHEN** a customer submits an override referencing another customer’s place
- **THEN** the system rejects the write and leaves prior overrides unchanged

### Requirement: Resolution precedence is deterministic
For a given customer, service date, and meal period, the system SHALL resolve the effective place in this order: (1) active weekday override for that date’s weekday and meal period; (2) else the period’s default preference place if active; (3) else the documented fallback (migrated/default place). Weekday MUST be computed in the project meal timezone (`Asia/Dhaka`).

#### Scenario: Override wins over default
- **WHEN** lunch default is Home and Wednesday lunch override is Office
- **THEN** resolving lunch on a Wednesday returns Office

#### Scenario: Default used when no override
- **WHEN** dinner default is Home and no override exists for that weekday
- **THEN** resolving dinner on that date returns Home

#### Scenario: Weekend falls back to default after weekday-only overrides
- **WHEN** lunch overrides exist only for weekdays and Saturday has no override
- **THEN** resolving Saturday lunch returns the lunch default place

### Requirement: Preference UX remains simple for clients
The system SHALL expose preference read/write APIs that support a simple client flow: choose usual lunch place, choose usual dinner place, optionally configure weekday exceptions. The system SHOULD provide a preview of resolved destinations over a date range so clients can show customers where meals will go without teaching resolution rules.

#### Scenario: Preferences read returns defaults and overrides
- **WHEN** an authenticated customer with defaults and overrides requests delivery preferences
- **THEN** the response includes lunch/dinner place identities and the override list

#### Scenario: Preview week destinations
- **WHEN** an authenticated customer requests a delivery preference preview for a date range
- **THEN** the system returns the resolved place (or snapshot fields) per date and meal period for that customer
