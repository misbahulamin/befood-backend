## ADDED Requirements

### Requirement: Clients can read location confirmation status
The system SHALL expose clear, documented fields so clients can determine whether the customer already has a confirmed/saved delivery location and whether a guest location offer is still pending. “Location confirmed” for this purpose MUST mean an active location preference with a saved location (`saved.exists == true`), not `CustomerDeliveryPlace.is_verified_location` and not a one-off service-area `verified` flag.

#### Scenario: Preference payload includes confirmation flags
- **WHEN** an authenticated customer calls `GET .../location-preference/` and a saved location exists
- **THEN** the response includes additive fields indicating `has_saved_location` / `location_confirmed` as true (names as documented) alongside existing `saved` data

#### Scenario: No saved location
- **WHEN** an authenticated customer has no active saved location preference
- **THEN** confirmation flags are false (or preference `exists` is false per existing empty contract) and clients MUST treat the location as not yet confirmed for skip-popup purposes

### Requirement: Guest offer payload includes explicit status
When returning a guest offer result, the system SHALL include an explicit `status` value such as `pending`, `accepted`, `declined`, `suppressed`, or `none` so clients do not infer state only from side effects.

#### Scenario: Pending offer status
- **WHEN** GET guest-offer finds an unresolved offer
- **THEN** the response includes `exists: true` and `status: pending` (or equivalent documented pending value)

#### Scenario: Resolved offer status
- **WHEN** GET guest-offer finds a resolved or suppressed offer
- **THEN** the response includes `exists: false` and a non-pending `status`

### Requirement: Optional lean summary on identity endpoints
The system MAY include an additive lean `location_confirmation` summary on login and/or `GET .../me/` with at least `has_saved_location` / `location_confirmed`. If included, the summary MUST be read-only and MUST NOT remove existing login fields.

#### Scenario: Additive login summary does not break clients
- **WHEN** login succeeds and the lean summary is enabled
- **THEN** existing token/user/profile fields remain present and the new object is additive

### Requirement: Confirmation state persists across sessions
Once a customer has a saved/confirmed delivery location via accept, save-as-place, or set-active-place, that confirmation state MUST remain until the customer clears the active saved preference or changes location through documented APIs. Normal login, logout, and app restart MUST NOT reset confirmation state.

#### Scenario: Login does not clear saved confirmation
- **WHEN** a customer with `location_confirmed` true logs out and logs in again
- **THEN** confirmation/saved status remains true and guest-offer remains non-pending for previously resolved sessions
