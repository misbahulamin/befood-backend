## ADDED Requirements

### Requirement: Customer location preference separates detected and saved location
The system SHALL maintain at most one `CustomerLocationPreference` per authenticated customer profile. The preference MUST store independently: (1) optional `active_delivery_place` plus denormalized `saved_latitude`, `saved_longitude`, optional saved location name, and `saved_at`; (2) optional `last_detected_latitude`, `last_detected_longitude`, optional detected name/accuracy, and `detected_at`. Guests MUST NOT receive a persisted preference. Refreshing GPS without saving MUST update detected fields only and MUST NOT change saved fields or the linked delivery place.

#### Scenario: Get preference with both detected and saved
- **WHEN** an authenticated customer has a saved active place and a later GPS detect at a different coordinate
- **THEN** `GET` location-preference returns both saved and last-detected coordinates with their respective timestamps

#### Scenario: Get when unset
- **WHEN** an authenticated customer has no preference row (or empty preference)
- **THEN** the system responds `200` with `exists=false` (or equivalent) without error

#### Scenario: Unauthenticated rejected
- **WHEN** an unauthenticated client calls location-preference endpoints
- **THEN** the system responds `401 Unauthorized`

### Requirement: Location preference API surface
The system SHALL expose under the customer location-preference resource: `GET /` to read preference; `PATCH .../refresh/` to update last-detected location only; `POST .../save-as-place/` to persist a delivery place from detected or explicit coordinates and update saved fields. Clearing/deactivating preference MUST NOT delete underlying delivery places.

#### Scenario: Refresh updates detected only
- **WHEN** a customer calls refresh with new GPS coordinates while a saved place exists
- **THEN** `detected_at` and last-detected coords update and saved coords / `active_delivery_place` remain unchanged

#### Scenario: Save-as-place creates delivery place and updates saved
- **WHEN** a customer calls save-as-place with required label, address text, coordinates, and source
- **THEN** a delivery place is created (subject to limit/duplicate rules), saved fields and `saved_at` update, and `active_delivery_place` may be set

#### Scenario: Clear preference keeps places
- **WHEN** a customer clears/deactivates location preference
- **THEN** subsequent get reports no active preference and delivery places remain

### Requirement: Saving location does not auto-change meal defaults
The system MUST NOT modify `MealDeliveryPreference` lunch/dinner places solely because a location was refreshed or saved as a place. Optional request flags (e.g. set default delivery / set lunch / set dinner) MUST default to false and apply only when explicitly true after client UI confirmation.

#### Scenario: Save without meal flags leaves lunch dinner unchanged
- **WHEN** a customer save-as-place without meal-default flags
- **THEN** lunch and dinner preference FKs are unchanged

#### Scenario: Explicit lunch flag updates only when requested
- **WHEN** a customer save-as-place with an explicit lunch-default opt-in flag true
- **THEN** the new or selected place becomes the lunch default and dinner is unchanged unless also opted in

### Requirement: Refresh interval guides client GPS reuse
The system SHALL expose `can_refresh` and `expires_at` based on `detected_at` (documented fallback if only saved exists) and `location_refresh_interval_hours` (default 24). Explicit refresh and save-as-place MUST always be accepted regardless of freshness. Soft accuracy warning rules apply on refresh when accuracy is provided.

#### Scenario: Fresh detection reports not stale
- **WHEN** `detected_at` is within the configured refresh interval
- **THEN** GET indicates the detection is fresh (`can_refresh` false or `stale` false per contract)

#### Scenario: Explicit refresh always allowed
- **WHEN** a customer PATCHes refresh before the interval elapses
- **THEN** the system accepts and updates detected fields

### Requirement: Low GPS accuracy yields soft warning on preference APIs
When refresh or save-as-place includes `accuracy` greater than `SERVICE_AREA_ACCURACY_THRESHOLD_M` (default 500), the system SHALL still succeed and MUST include `warning_code=LOW_LOCATION_ACCURACY` (same code as service-area check). Omitted accuracy MUST NOT trigger this warning.

#### Scenario: Accuracy 187 under threshold succeeds without low-accuracy warning
- **WHEN** refresh sends accuracy 187 and threshold is 500
- **THEN** the system updates detected location without `LOW_LOCATION_ACCURACY`

#### Scenario: Accuracy above threshold warns but saves
- **WHEN** refresh or save-as-place sends accuracy 600 with threshold 500
- **THEN** the system succeeds and includes `warning_code=LOW_LOCATION_ACCURACY`
