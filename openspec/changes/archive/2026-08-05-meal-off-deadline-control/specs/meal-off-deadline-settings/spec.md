## MODIFIED Requirements

### Requirement: Deadline math uses configured times

The system MUST compute lunch and dinner meal-off deadlines from the settings as:

- lunch on `D` → `(D − 1) + lunch_off_time`
- dinner on `D` → `D + dinner_off_time`

in the configured timezone, and MUST compare against the current time in that timezone. The same computed deadline MUST gate both customer meal-off and customer meal-on eligibility for that slot.

#### Scenario: Custom lunch off time moves deadline

- **WHEN** `lunch_off_time` is `22:00:00` and a customer meal-offs lunch for `2026-07-24` at business time `2026-07-23 22:30`
- **THEN** the system rejects the request because the lunch deadline has passed

#### Scenario: Same deadline blocks meal-on after cutoff

- **WHEN** `dinner_off_time` is `21:00:00`, dinner for `2026-08-05` was meal-offed earlier, and business time is `2026-08-05 21:01` in the settings timezone
- **THEN** meal-on for that dinner is rejected because the dinner deadline has passed

#### Scenario: Before configured dinner time meal-on remains allowed

- **WHEN** `dinner_off_time` is `21:00:00`, dinner for `2026-08-05` is customer-skipped, and business time is `2026-08-05 20:59`
- **THEN** meal-on for that dinner is allowed by the deadline check
