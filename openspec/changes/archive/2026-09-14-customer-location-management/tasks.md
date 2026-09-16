## 1. Models and migrations

- [x] 1.1 Add `location_source` (incl. `guest_migration`), `location_accuracy`, `formatted_address`, `is_verified_location` to `CustomerDeliveryPlace` with safe defaults
- [x] 1.2 Add singleton `CustomerLocationSettings` (`duplicate_radius_km`, `max_active_delivery_places`, `location_refresh_interval_hours`) with `.load()` / pk=1
- [x] 1.3 Add `CustomerLocationPreference` with `active_delivery_place`, `saved_*` + `saved_at`, `last_detected_*` + `detected_at`, `is_active`
- [x] 1.4 Register new models in Django admin; generate and apply migrations

## 2. Location services

- [x] 2.1 Add location helper wrapping Haversine, coordinate validation, accuracy reliability (`LOW_LOCATION_ACCURACY` / existing threshold), reverse_geocode stub
- [x] 2.2 Update create/update delivery place: settings-based max (`ADDRESS_LIMIT_REACHED`), location metadata, geo-source validation (incl. `guest_migration`)
- [x] 2.3 Implement duplicate-within-radius check with **exclude current place id** on update (`LOCATION_ALREADY_EXISTS`)
- [x] 2.4 Implement preference GET payload (saved vs detected) and freshness (`can_refresh` / `expires_at` from `detected_at`)
- [x] 2.5 Implement `refresh` service: update last-detected fields only; soft accuracy warning
- [x] 2.6 Implement `save-as-place` service: create place, update saved fields; meal-default flags default false (no auto lunch/dinner)
- [x] 2.7 Implement guest-offer lookup/accept with `location_source=guest_migration` (dupe/limit rules; no auto meal defaults)

## 3. API layer

- [x] 3.1 Extend delivery-place serializers/views/OpenAPI for new fields, self-excluded duplicate errors, accuracy warnings where applicable
- [x] 3.2 Add `GET /user_management/customer/location-preference/`
- [x] 3.3 Add `PATCH /user_management/customer/location-preference/refresh/`
- [x] 3.4 Add `POST /user_management/customer/location-preference/save-as-place/`
- [x] 3.5 Add guest-offer endpoint under location-preference
- [x] 3.6 Add verified-admin web API for `CustomerLocationSettings`
- [x] 3.7 Extend `POST /api/v1/service-areas/check/` with additive `saved_location` for authenticated customers

## 4. Documentation

- [x] 4.1 Frontend/mobile guide: GET preference, PATCH refresh, POST save-as-place, detected vs saved examples
- [x] 4.2 Document permission-denied UX (show saved; no permission spam) and meal-default / lunch-dinner separate opt-in popups
- [x] 4.3 Document duplicate/limit/accuracy codes, `guest_migration`, admin settings + accuracy env threshold
- [x] 4.4 Update service-area frontend doc for optional `saved_location` (backward compatible)

## 5. Testing

- [x] 5.1 Tests: GPS / manual / map_pin / search / guest_migration save paths and geo validation failures
- [x] 5.2 Tests: duplicate on create; update self-exclude; update colliding with another place; outside radius
- [x] 5.3 Tests: address limit, admin-raised limit, grandfather above lower limit
- [x] 5.4 Tests: refresh updates detected only; save-as-place updates saved; GET returns both; freshness flags
- [x] 5.5 Tests: save-as-place does not change lunch/dinner unless explicit flags; accuracy soft warning above threshold
- [x] 5.6 Tests: guest offer accept with `guest_migration`; accept blocked by dupe/limit; guest check creates no place
- [x] 5.7 Regression: service-area check legacy payload/response + existing `LOW_LOCATION_ACCURACY`; meal preference resolution unchanged

## 6. Verification

- [x] 6.1 Run targeted user_management + service_area tests and fix failures
- [x] 6.2 Spot-check OpenAPI/schema examples for new and extended endpoints
