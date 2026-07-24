## ADDED Requirements

### Requirement: Ops catalog resources may adopt public UUID identity

When the ops-catalog phase is implemented, `Ingredient`, `MealCycle`, `MealCyclePlan`, `MealCyclePlanLine`, and `MonthlyMenuSchedule` SHALL each gain `public_id` with the shared convention. Manager API lookup and URL identity for those resources MUST use `public_id` after that phase cutover.

#### Scenario: Cycle plan detail by UUID after ops phase

- **WHEN** the ops-catalog phase is live and a manager retrieves a cycle plan by UUID
- **THEN** the plan is returned and integer plan paths no longer resolve

### Requirement: Nested admin meal references

After the ops-catalog phase, nested admin serializers that currently expose only integer meal/plan ids SHOULD expose `public_id` (and may retain integer `id` only if explicitly required for a transitional admin tool). New manager UI work MUST prefer UUID fields.

#### Scenario: Plan serializer exposes meal public_id

- **WHEN** a cycle plan response includes meal category identity after ops phase
- **THEN** the meal’s `public_id` is present for client navigation
