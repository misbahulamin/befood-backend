## ADDED Requirements

### Requirement: Published package menu slots may expose final meal price

When a verified customer retrieves their published package menu for a month, each returned lunch or dinner slot MAY include a read-only `final_meal_price` equal to the published slot’s stored final selling price snapshot. When the schedule is not published, day/slot lists remain empty and MUST NOT invent live prices. The system MUST NOT replace per-slot prices with the package average `per_meal_rate` in this field.

#### Scenario: Published slot includes final meal price when exposed

- **WHEN** a verified customer requests package menu for a published schedule and the API exposes slot pricing
- **THEN** each slot’s `final_meal_price` matches that slot’s stored published snapshot, and lunch and dinner on the same day may differ

#### Scenario: Unpublished package still returns empty days

- **WHEN** a verified customer has an active order for the month but the package schedule is not published
- **THEN** `schedule_published` is `false`, days/slots are empty, and no fabricated `final_meal_price` values are returned
