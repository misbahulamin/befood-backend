## ADDED Requirements

### Requirement: Late low-balance resume must not inflate past-cutoff cooking counts

After a customer’s low-balance meal-stop block is cleared because wallet balance recovered, the kitchen today-requirement for a `(service_date, meal_period)` whose meal-off cutoff has already passed MUST NOT increase `final_cooking_count` solely due to that resume. Ingredient quantities that scale from `final_cooking_count` MUST remain consistent with that stable cooking headcount. A late-resumed customer MAY move from `low_balance_blocked_count` into meal-off/skipped accounting for that slot, but MUST NOT appear in final cooking for an already-cutoff-passed period.

#### Scenario: Morning kitchen count stays flat after late lunch resume

- **WHEN** lunch cutoff has passed, kitchen lunch `final_cooking_count` is `30`, and a previously low-balance-blocked customer recharges and resumes
- **THEN** lunch `final_cooking_count` remains `30` and ingredient kg derived from final cooking do not increase for that customer

#### Scenario: Dinner requirement can include customer before dinner cutoff

- **WHEN** the same customer resumes after lunch cutoff but before dinner cutoff with dinner meal ON (`scheduled`)
- **THEN** dinner kitchen requirement MAY include the customer in `final_cooking_count` while lunch remains excluded
