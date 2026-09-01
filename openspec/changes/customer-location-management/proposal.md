## Why

Service-area check today only verifies GPS temporarily and never persists a customer’s location, so React/Flutter clients must re-request permission every visit and cannot reuse coordinates with the existing delivery place book. We need a complete location lifecycle—detect (including last-detected vs saved place), save into `CustomerDeliveryPlace`, cache preference, dedupe nearby pins (excluding self on update), enforce admin limits, migrate guest checks on login, and surface accuracy warnings—without breaking `/api/v1/service-areas/check/` or auto-changing meal delivery defaults.

## What Changes

- Extend `CustomerDeliveryPlace` with GPS metadata (`location_source`, accuracy, formatted address, verified flag) while keeping lat/lng + address book as the single saved-location store (no parallel address system).
- `location_source` values: `gps` | `manual` | `map_pin` | `search` | `guest_migration` | empty (legacy).
- Add admin-configurable singleton settings: duplicate radius (default 0.5 km), max active delivery places (default 3; replaces hardcoded `10`), and location refresh interval (default 24h).
- Add `CustomerLocationPreference` that **separates** last-detected GPS from saved delivery place coords (`last_detected_*` + `detected_at` vs `active_place` + `saved_*` + `saved_at`) for UX and future analytics.
- Explicit APIs: `GET .../location-preference/`, `PATCH .../location-preference/refresh/` (updates detected only), `POST .../location-preference/save-as-place/` (persists as delivery place).
- Saving a place MUST NOT auto-update lunch/dinner defaults; clients MAY pass explicit opt-in flags after user confirms separate popups.
- Duplicate-near-place detection on create **and** geo-update; updates MUST exclude the current place’s id.
- Soft accuracy warning when `accuracy` exceeds threshold (reuse `SERVICE_AREA_ACCURACY_THRESHOLD_M` / `LOW_LOCATION_ACCURACY`); does not block save/check.
- Guest locations remain non-persistent as places; on login/register, offer migration with `location_source=guest_migration`.
- Additive `saved_location` on service-area check for authenticated users (**backward compatible**).
- Client docs: permission-denied → show saved location, do not re-prompt GPS spam; meal-default / lunch-dinner as separate UI choices.
- Thin `LocationService` abstraction; React + Flutter docs and tests.

**BREAKING (soft product behavior):** default max active delivery places changes from code constant `10` to admin setting default `3`. Customers already above the new limit keep existing places but cannot create more until under the limit. Error codes for limit/duplicate become explicit machine-readable codes.

## Capabilities

### New Capabilities
- `customer-location-preference`: Detected vs saved location preference, refresh/save-as-place APIs, refresh policy, accuracy soft-warnings for logged-in customers.
- `delivery-place-location-enrichment`: GPS/map/manual/guest_migration metadata, required coordinates for geo saves, duplicate-within-radius rejection (exclude self on update), configurable address limit.
- `guest-location-migration`: After auth, offer saving the latest guest service-area check location as a delivery place with `guest_migration` source.
- `customer-location-admin-settings`: Singleton admin settings for duplicate radius, max addresses, and refresh interval (Django admin + optional web API).
- `customer-location-client-docs`: Frontend/mobile guides covering detect → refresh → save-as-place, permission-denied UX, meal-default opt-in, guest migration.
- `service-area-check-location-hints`: Additive optional `saved_location` on `POST /api/v1/service-areas/check/` for authenticated customers without changing existing fields.

### Modified Capabilities
- `delivery-address-book`: Soft cap becomes admin-configurable (default 3); create/update gains location metadata, duplicate detection (self-excluded on update), and stronger coordinate requirements for geo flows.

## Impact

- **Apps:** `user_management` (models, delivery place services/views/serializers, preference + settings), `service_area` (check response extension, reuse geo + accuracy threshold).
- **APIs:** Enriched delivery-places; `GET/PATCH refresh/POST save-as-place` under `/user_management/customer/location-preference/`; guest offer; admin settings; additive check fields.
- **DB:** Migrations on `CustomerDeliveryPlace`; new `CustomerLocationPreference` (detected + saved fields) + `CustomerLocationSettings`.
- **Clients:** React + Flutter; guests keep `X-Guest-Session-Id` / `guest_session_id`.
- **Tests/docs:** Delivery-address, preference (detected≠saved), duplicate self-exclude, accuracy warning, guest_migration source, meal-default not auto-applied.
