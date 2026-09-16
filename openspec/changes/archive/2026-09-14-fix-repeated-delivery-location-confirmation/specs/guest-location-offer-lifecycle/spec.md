## ADDED Requirements

### Requirement: Guest location offer resolution is durable per customer
The system SHALL persist a resolution for each pair of authenticated customer and `guest_session_id` with status `accepted` or `declined` (and MAY use `suppressed` when the offer is auto-closed because an equivalent saved place already exists). Resolutions MUST survive logout, app restart, and subsequent logins.

#### Scenario: Accept records accepted resolution
- **WHEN** an authenticated customer successfully accepts a guest location offer for a `guest_session_id`
- **THEN** the system stores resolution status `accepted` for that customer and session and does not leave the offer in a pending state

#### Scenario: Decline records declined resolution
- **WHEN** an authenticated customer declines a guest location offer for a `guest_session_id` via the decline API
- **THEN** the system stores resolution status `declined` for that customer and session and does not create a delivery place

### Requirement: Guest offer GET returns exists false after resolution
The system SHALL evaluate guest offers for the authenticated customer. `GET .../location-preference/guest-offer/` MUST return `exists: false` when a resolution already exists for that customer and `guest_session_id`, even if `ServiceAreaRequest` rows for the session still exist.

#### Scenario: Re-login after accept does not re-offer
- **WHEN** a customer who previously accepted an offer for session S requests the guest offer for S again after logout and login
- **THEN** the response is `200` with `exists: false` (and status indicating accepted or equivalent)

#### Scenario: Re-login after decline does not re-offer
- **WHEN** a customer who previously declined an offer for session S requests the guest offer for S again
- **THEN** the response is `200` with `exists: false` (and status indicating declined or equivalent)

#### Scenario: First pending offer still available
- **WHEN** an authenticated customer requests a guest offer for a session with a prior service-area check and no resolution for that customer
- **THEN** the response is `200` with `exists: true` and pending offer coordinates

### Requirement: Equivalent saved location suppresses the offer
The system SHALL NOT present a pending guest offer when the customer already has an active saved delivery location that is equivalent to the latest guest check for that session within the configured duplicate radius (or an existing active delivery place within that radius). In that case GET MUST return `exists: false`.

#### Scenario: Duplicate place suppresses pending offer
- **WHEN** the latest guest check for session S matches an existing active delivery place for the customer within duplicate radius
- **THEN** GET guest-offer returns `exists: false` and MUST NOT require the client to show a confirmation popup

### Requirement: Decline API is available
The system SHALL provide an authenticated decline operation for guest location offers that records durable dismissal without creating a delivery place.

#### Scenario: Decline succeeds
- **WHEN** an authenticated customer submits a valid decline for a pending `guest_session_id`
- **THEN** the system responds success, stores `declined`, and subsequent GET for that pair returns `exists: false`

#### Scenario: Decline is idempotent
- **WHEN** the customer declines an already declined or already accepted offer for the same session
- **THEN** the system responds success without creating a place and leaves a non-pending resolution in place
