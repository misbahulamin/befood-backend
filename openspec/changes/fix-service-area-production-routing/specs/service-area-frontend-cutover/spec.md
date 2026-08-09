## ADDED Requirements

### Requirement: Admin client uses web service-area base path
The admin frontend MUST call `{API_BASE}/api/v1/web/service-areas/` with a verified admin Token for hub list, create, update, soft-delete, status, request history, and analytics summary.

#### Scenario: List hubs after backend release
- **WHEN** the admin opens the Service Areas page after the backend release
- **THEN** the client MUST request `GET /api/v1/web/service-areas/?page=&page_size=`
- **AND** MUST treat a non-JSON HTML 404 as an API outage state (not an empty hub list)

#### Scenario: Create hub from map
- **WHEN** an admin picks a map point and radius and submits create
- **THEN** the client MUST `POST /api/v1/web/service-areas/` with `name`, `latitude`, `longitude`, `radius_km`, and optional `description` / `is_active`
- **AND** MUST refresh the list from the API response or a follow-up list call

### Requirement: Customer client verifies coverage via check API
The customer frontend MUST obtain browser/device or map pin coordinates and call `POST /api/v1/service-areas/check/`; it MUST NOT use IP geolocation and MUST NOT authorize checkout using client-side distance math alone.

#### Scenario: Delivery box verification
- **WHEN** a guest or customer verifies the Delivery address box
- **THEN** the client MUST send latitude and longitude to `POST /api/v1/service-areas/check/`
- **AND** MUST render UI from `service_available`, `location_reliable`, matched/nearest hub fields, and `distance_km`

#### Scenario: Demand CTA
- **WHEN** coverage is unavailable and the user chooses “want BeFood here”
- **THEN** the client MUST `POST /api/v1/service-areas/demand/` with the same coordinate payload shape
- **AND** MUST NOT treat a successful demand response as unlocking checkout

### Requirement: Customer client handles order gate errors
The customer order-create flow MUST handle service-area validation failures by reading machine-readable error codes and guiding the user back to location selection.

#### Scenario: Missing delivery coordinates on order
- **WHEN** order create fails with `DELIVERY_LOCATION_REQUIRED`
- **THEN** the UI MUST prompt the user to set a map/GPS delivery location
- **AND** MUST NOT silently retry without updating coordinates

#### Scenario: Outside service area on order
- **WHEN** order create fails with `SERVICE_AREA_UNAVAILABLE`
- **THEN** the UI MUST explain that BeFood does not serve that delivery location
- **AND** MAY offer the demand CTA using the check/demand APIs

### Requirement: Frontend docs remain the contract source
Backend-maintained frontend docs under `service_area/docs/frontend/` MUST stay aligned with the released paths, headers, bodies, and error codes used by admin and customer clients.

#### Scenario: Doc paths match live routes
- **WHEN** a frontend engineer follows `admin-service-areas.md` or `customer-service-area.md`
- **THEN** every documented path MUST resolve on the released backend (not URL 404)
- **AND** documented error codes for checkout MUST match the order serializer contract
