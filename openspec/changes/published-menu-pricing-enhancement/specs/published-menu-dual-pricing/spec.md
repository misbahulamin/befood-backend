## ADDED Requirements

### Requirement: Published menu dual pricing contract for admin clients

The system SHALL expose a backend dual-pricing contract for admin published-menu views so clients can render ingredient cost, subscriber price/profit, and Instant price/profit without performing pricing arithmetic. Backend responses MUST be the single source of truth for these amounts.

#### Scenario: Admin UI can render cost and both ladders from API only

- **WHEN** an admin published-menu client receives a priced slot payload with selected ingredient cost, operational cost, `subscriber_pricing`, and `instant_pricing`
- **THEN** the client can display ingredient cost, subscriber price, subscriber profit, Instant price, and Instant profit using response fields only

#### Scenario: Worked Instant example matches backend

- **WHEN** ingredient cost is `48.15`, operational cost is `4.13`, and Instant profit percent is `70.00`
- **THEN** Instant profit amount is `33.71` and Instant final price is `85.99` (decimal half-up to money precision)

### Requirement: Backward-compatible subscriber price field

Admin dual-pricing enrichment MUST keep the historical subscriber selling-price field used by existing published-menu clients (`final_meal_price` and/or `price` where already present) and MAY add `subscriber_price` / `instant_price` aliases. The system MUST NOT remove the legacy subscriber price field in this change.

#### Scenario: Legacy price field retained

- **WHEN** dual-pricing fields are added to admin published menu / schedule assignment payloads
- **THEN** the legacy subscriber price field remains populated with the same subscriber selling amount as before the enrichment
