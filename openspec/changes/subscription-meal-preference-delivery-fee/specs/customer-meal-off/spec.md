## ADDED Requirements

### Requirement: Meal OFF/ON only applies to existing preference periods

Meal preference (which periods a subscription includes) and meal OFF/ON (temporarily skip an included slot) MUST remain separate. The system MUST NOT create dinner delivery rows for lunch-only subscriptions (or lunch for dinner-only) for the purpose of meal OFF/ON. Customer meal OFF/ON endpoints continue to operate only on owned `OrderDelivery` rows that already exist.

#### Scenario: Lunch-only subscriber has no dinner slot to toggle

- **WHEN** a lunch-only subscription is active
- **THEN** ensure does not create dinner rows, so the customer has no dinner meal-off target for those dates

#### Scenario: Both subscriber meal-off lunch unchanged

- **WHEN** a both-preference subscriber meal-offs a scheduled lunch before deadline
- **THEN** that lunch row becomes `skipped` with customer skip source and dinner rows for the same date remain unaffected
