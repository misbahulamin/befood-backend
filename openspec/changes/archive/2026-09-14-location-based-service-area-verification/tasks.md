## 1. App scaffold and models

- [x] 1.1 Create `service_area` Django app package (`models`, `services`, `api`, `admin`, `tests`, `docs`) and register it in `INSTALLED_APPS`
- [x] 1.2 Implement `ServiceArea` model (`public_id`, `name`, `latitude`, `longitude`, `radius_km`, `is_active`, `description`, `created_by`, timestamps) with validation constraints
- [x] 1.3 Implement `ServiceAreaRequest` model (`public_id`, user/customer FK nullable, `guest_session_id`, coords, `accuracy`, location name fields, matched hub FK, `distance_km`, `is_serviceable`, `request_kind`, timestamps) with indexes for analytics
- [x] 1.4 Generate and apply migrations; register models in Django admin for ops fallback

## 2. Geo and verification services

- [x] 2.1 Implement Haversine distance helper in `service_area/services/geo.py` with unit tests for known Chattogram-scale pairs
- [x] 2.2 Implement matching service: active hubs only, nearest covering hub, else nearest hub + `service_available=false`
- [x] 2.3 Implement check orchestration: validate coords, compute reliability from accuracy threshold (default 500 m), persist `ServiceAreaRequest` (`request_kind=check`), build response DTO
- [x] 2.4 Implement demand orchestration (`request_kind=demand`) reusing location persistence without granting serviceability
- [x] 2.5 Expose `assert_serviceable(lat, lng)` (or equivalent) for order-create gate with stable error codes

## 3. Customer / shared verification APIs

- [x] 3.1 Add serializers for check/demand request and response (`customer_location`, `matched_service_area` / `nearest_service_area`, `distance_km`, `location_reliable`, warning code)
- [x] 3.2 Implement `POST /api/v1/service-areas/check` (guest + optional auth) and demand endpoint; accept `guest_session_id` body or header
- [x] 3.3 Mount routes in `core/urls.py`; add OpenAPI helpers with examples for available/unavailable/low-accuracy
- [x] 3.4 Ensure IP geolocation is never used; document that only request body coordinates drive matching

## 4. Admin web APIs and analytics

- [x] 4.1 Implement verified-admin CRUD serializers/views for hubs under `/api/v1/web/service-areas/` (list paginated, create, retrieve, patch, delete/soft-delete, activate/deactivate)
- [x] 4.2 Implement analytics endpoints: top requested areas, top non-serviceable locations (counts + average distance), paginated raw request list with allowlisted date filters
- [x] 4.3 Enforce `IsVerifiedAdmin` (and optional group permission codenames); reject unsupported filters with `400`
- [x] 4.4 Add OpenAPI helpers for all admin endpoints

## 5. Order checkout service-area gate

- [x] 5.1 Hook `assert_serviceable` into meal package order create after delivery place/coordinate resolution
- [x] 5.2 Map missing coordinates and out-of-coverage failures to clear API validation/`error_code` responses without creating the order
- [x] 5.3 Confirm client “already verified” flags are ignored; re-check uses current active hubs

## 6. Tests

- [x] 6.1 Service tests: inside radius, outside radius, multi-hub nearest covering, inactive hub ignored, no active hubs
- [x] 6.2 API tests: check guest/auth, null location_name, low accuracy warning, demand persistence, validation errors
- [x] 6.3 Admin API permission and CRUD/status tests; analytics aggregation smoke tests
- [x] 6.4 Order-create gate tests: serviceable allows (other rules aside), unserviceable rejects, missing lat/lng rejects, hub deactivated after prior check rejects

## 7. Documentation

- [x] 7.1 Write `service_area/docs/backend/service-area-verification.md` (models, Haversine rules, APIs, history, checkout gate, error codes, verify steps)
- [x] 7.2 Write `service_area/docs/frontend/customer-service-area.md` (Home delivery box states, geolocation-only, cache TTL, manual pin/search, demand CTA, checkout revalidation)
- [x] 7.3 Write `service_area/docs/frontend/admin-service-areas.md` (table, map picker + radius circle, CRUD, analytics field mapping)
- [x] 7.4 Run relevant tests and fix failures; smoke-check new endpoints in OpenAPI/Swagger if available
