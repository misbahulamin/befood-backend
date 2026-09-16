## Why

BeFood customers can already save delivery places with coordinates, but nothing proves those coordinates fall inside an operable delivery hub. Without radius-based service-area verification, Home/checkout can accept orders from non-serviceable locations, and expansion decisions lack demand signal from denied or out-of-range visitors. Device geolocation (not IP) plus backend Haversine matching against admin-managed hubs closes that gap for customer frontend, backend, and verified admin.

## What Changes

- Add a dedicated **Service Area** domain: admin-managed hubs with name, latitude, longitude, radius (km), active flag, and description—independent of customer “area name” strings.
- Expose a **public/customer verification API** that accepts browser/device geolocation (`latitude`, `longitude`, `accuracy`, optional `location_name`) and returns serviceability based on geographic distance to active hubs (never name equality).
- Support **multiple active hubs**: match the nearest hub whose radius covers the customer; if none cover, return nearest hub + distance for UX and demand capture.
- Persist every verification attempt in **request history** (guest session or logged-in user) for analytics and future expansion decisions; support an explicit “I want BeFood in my area” demand signal when unavailable.
- Enforce **checkout / order-create revalidation** on the backend using delivery coordinates so frontend cache or UI state cannot bypass serviceability.
- Add **Verified Admin web APIs** for hub CRUD, activate/deactivate, and request/demand analytics summaries (top areas, top non-serviceable locations).
- Ship **frontend contract docs** for customer Home delivery box (permission, loading, low-accuracy, manual pin/search, cache) and Admin Service Areas UI (map picker + radius preview).
- Clarify that existing `business.DeliveryZone` (fee/outlet) is **not** reused as the serviceability gate; this change introduces a dedicated hub model/API for coverage verification.
- **Out of scope for this change:** full GIS polygon zones, rider routing, IP geolocation, replacing customer delivery-address book, automatic stock/ops assignment by hub, live push notifications for demand, production Google Maps billing ops beyond documented API-key usage.

## Capabilities

### New Capabilities
- `service-area-management`: Admin-managed service hubs (name, coordinates, radius_km, status, description) used as the sole geographic coverage source of truth.
- `service-area-verification`: Customer/guest check API: Haversine (or equivalent) distance matching against active hubs, accuracy handling, separated customer location vs matched hub in the response; final decision always server-side.
- `service-area-request-history`: Persist verification and demand requests (user or guest), including coordinates, accuracy, detected name, match/nearest hub, distance, and serviceability for analytics.
- `service-area-admin-api`: Verified-admin web APIs for hub CRUD/status and request analytics (top requested / top non-serviceable areas).
- `order-service-area-gate`: Order/checkout creation MUST re-validate delivery latitude/longitude against active hubs and reject non-serviceable destinations.
- `service-area-frontend-docs`: Customer Home delivery-box + Admin Service Areas UI contracts (states, API usage, map pin/search, cache rules).

### Modified Capabilities
- _(none)_ — existing `delivery-address-book` / `delivery-address-resolution` remain address storage and slot snapshots; they do not define coverage. Order status lifecycle specs are unchanged; serviceability is a new create-time gate.

## Impact

- **New app** (recommended): `service_area/` with models, services (distance + matching), customer/shared check endpoint, web admin routes under `/api/v1/web/service-areas/`, tests, `docs/backend` + `docs/frontend`.
- **Orders:** create/checkout path in `orders/services` gains a service-area eligibility check using resolved delivery coordinates (or explicit lat/lng on the request when applicable).
- **User management:** delivery places already store lat/lng; no breaking address-book contract, but checkout gate depends on those coordinates being present/valid.
- **Auth:** guest-friendly check + history (session/anonymous id); admin mutations require verified admin / group permissions consistent with other `/api/v1/web/` modules.
- **Clients:** `befood_frontend` Home delivery box + checkout revalidation; Admin frontend Service Areas section + map picker (Google Maps). Reverse geocoding may run client-side and/or backend-assisted; verification never uses IP location.
- **Dependencies:** Decimal-safe distance math (Haversine); optional Google Geocoding/Maps keys via env; no PostGIS required for v1 unless design chooses it.
- **Docs/tests:** Backend technical docs, frontend contracts, OpenAPI, and tests for match/nearest/accuracy/inactive hubs/guest history/checkout rejection.
