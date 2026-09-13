## ADDED Requirements

### Requirement: Post-resume cutoff skips feed meal-off not final cooking

Shared meal-demand calculation MUST treat deliveries system-skipped after low-balance resume (because the slot’s meal-off cutoff had already passed) as meal-off/skipped for that `(service_date, meal_period)`, not as final cooking. Clearing `meal_service_blocked_low_balance` alone MUST NOT move a still-`scheduled` past-cutoff delivery into the cooking set. The existing demand invariant across expected, meal-off, low-balance-blocked, and final cooking counts MUST remain consistent after such a transition.

#### Scenario: Blocked then late-resumed lunch moves to meal-off bucket

- **WHEN** a customer’s lunch delivery was counted under low-balance blocked (not final cooking) and resume after lunch cutoff system-skips that lunch
- **THEN** demand for that lunch slot counts the delivery under meal-off (or equivalent skipped accounting), not under `final_cooking_count`, and not under `low_balance_blocked_count`

#### Scenario: Expected identity preserved without negative counts

- **WHEN** demand is recalculated immediately after late resume cutoff skip
- **THEN** counts remain non-negative and final cooking does not exceed the pre-resume final cooking for that past-cutoff slot due to the resumed customer
