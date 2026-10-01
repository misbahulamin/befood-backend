## ADDED Requirements

### Requirement: Guest meal orders appear in composed customer activity

The system SHALL include successful guest meal purchases in the admin composed customer activity feed with event type `guest_meal_ordered` (or the documented equivalent). Each event MUST include enough refs for audit: service date, meal period, quantity, total amount, and guest meal `public_id`. Callers without verified-admin permission MUST continue to be rejected. Activity composition MUST remain scoped to the requested customer only.

#### Scenario: Guest meal ordered appears in activity

- **WHEN** a verified admin requests activity for a customer who successfully ordered a guest meal
- **THEN** the results include a `guest_meal_ordered` event with date, meal period, quantity, total, and public id refs

#### Scenario: Other customer guest meals not leaked

- **WHEN** a verified admin requests activity for customer A
- **THEN** guest meal events belonging only to customer B MUST NOT appear
