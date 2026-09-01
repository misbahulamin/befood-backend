## ADDED Requirements

### Requirement: Guest location is not saved as a delivery place
The system SHALL NOT create `CustomerDeliveryPlace` rows for unauthenticated guests. Guest service-area checks MUST continue to use `guest_session_id` / `X-Guest-Session-Id` and existing `ServiceAreaRequest` persistence only.

#### Scenario: Guest check does not create delivery place
- **WHEN** a guest successfully calls service-area check with a guest session id
- **THEN** no delivery place is created for any customer

### Requirement: Authenticated customer can claim guest session location
After login or register, the system SHALL allow an authenticated customer to fetch an offer for the latest service-area request tied to a provided `guest_session_id` (coordinates and display name when available). Accepting the offer MUST create a delivery place with `location_source=guest_migration` (subject to duplicate and address-limit rules, self-exclusion N/A on create) and MAY update location-preference saved fields / active place. Accepting MUST NOT auto-change lunch/dinner defaults unless explicit opt-in flags are true. Declining MUST leave places unchanged.

#### Scenario: Guest offer available after login
- **WHEN** an authenticated customer requests a guest location offer for a session that has a prior service-area check
- **THEN** the system responds `200` with the latest check coordinates and location name

#### Scenario: Accept guest offer saves with guest_migration source
- **WHEN** the customer accepts the guest location offer with a label and required address fields
- **THEN** the system creates a delivery place with `location_source=guest_migration` owned by that customer

#### Scenario: No guest history
- **WHEN** the customer requests a guest offer for a session with no matching service-area request
- **THEN** the system responds `200` with `exists=false` (or equivalent) and does not create a place

#### Scenario: Accept blocked by duplicate or limit
- **WHEN** accepting the offer would violate duplicate radius or address limit
- **THEN** the system responds `422` with the corresponding `error_code` and does not create a place
