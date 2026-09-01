## ADDED Requirements

### Requirement: Frontend and mobile integration documentation
The system SHALL ship documentation sufficient for React and Flutter developers to implement location detect, refresh, save-as-place, reuse, update, delete, active preference (detected vs saved), duplicate/limit/accuracy warnings, guest migration, meal-default opt-in popups, and service-area check additive fields without reading backend source. Docs MUST include request/response examples, error/warning codes, recommended call order, and auth/header requirements (Token + optional `X-Guest-Session-Id`).

#### Scenario: Customer location API guide published
- **WHEN** this change is implemented
- **THEN** `user_management/docs/frontend/` includes a guide covering GET preference, PATCH refresh, POST save-as-place, and delivery-place enrichment

#### Scenario: Permission-denied UX documented
- **WHEN** this change is implemented
- **THEN** docs state that if OS location permission is denied, clients MUST show saved location (and last detected if any) and MUST NOT repeatedly prompt for permission; prompt only on explicit user action or when permission is already granted and refresh is allowed

#### Scenario: Meal default opt-in documented
- **WHEN** this change is implemented
- **THEN** docs describe separate UI confirmations for “save as default delivery location?” and optional lunch/dinner preference update, with API flags defaulting to false (no auto meal change)

#### Scenario: Guest migration documented
- **WHEN** this change is implemented
- **THEN** documentation describes guest check → login → offer → accept/decline with `guest_migration` source examples

#### Scenario: Admin settings documented
- **WHEN** this change is implemented
- **THEN** documentation lists the three location settings, defaults, accuracy threshold reuse, and client UX effects
