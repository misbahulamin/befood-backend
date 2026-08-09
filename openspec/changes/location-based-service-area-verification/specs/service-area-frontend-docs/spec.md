## ADDED Requirements

### Requirement: Customer frontend delivery-box contract docs
The system SHALL ship customer frontend documentation under `service_area/docs/frontend/` that explains how to wire the Home/Root delivery location box to browser geolocation and the backend check API. The document MUST cover: permission copy, loading states, permission-denied + manual address/search fallback, low-accuracy retry and map-pin fallback, serviceable/unserviceable UI including nearest hub, demand CTA, client cache/TTL rules, prohibition on client-side final distance gating, and checkout revalidation expectations. Documentation MUST state that IP-based location MUST NOT be used.

#### Scenario: Docs describe permission-denied fallback
- **WHEN** a frontend engineer reads the customer service-area docs
- **THEN** the docs explain showing “location access not granted” and offering manual address/map selection without blocking the entire website

#### Scenario: Docs forbid client-only coverage decisions
- **WHEN** a frontend engineer implements checkout enablement
- **THEN** the docs require trusting backend `service_available` / order-create errors and MUST NOT document a local `if (distance <= radius)` allow path as authoritative

### Requirement: Admin frontend service-areas contract docs
The system SHALL ship Admin Panel frontend documentation describing the Service Areas section: list table columns, create/edit forms, Google Map click-to-fill latitude/longitude, realtime radius circle preview, activate/deactivate/delete actions, and analytics views for top requested / top non-serviceable areas including endpoint paths, auth, and field meanings.

#### Scenario: Docs describe map picker + radius preview
- **WHEN** a frontend engineer implements hub create/edit
- **THEN** the docs explain map click → marker → lat/lng fields, radius input, and updating the drawn circle when radius changes

#### Scenario: Docs map analytics cards to API
- **WHEN** a frontend engineer implements demand analytics
- **THEN** the docs map top-area and top-non-serviceable UI blocks to the admin analytics response fields
