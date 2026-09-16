## Context

BeFood already ships three relevant systems:

1. **Service-area verification** (`service_area`): `POST /api/v1/service-areas/check/` accepts GPS + optional `location_name` / `guest_session_id`, runs Haversine matching against `ServiceArea` hubs, and persists history on `ServiceAreaRequest`. Soft warning `LOW_LOCATION_ACCURACY` when `accuracy` > `SERVICE_AREA_ACCURACY_THRESHOLD_M` (default 500). Coordinates are **not** saved as customer delivery destinations.
2. **Delivery place book** (`user_management`): `CustomerDeliveryPlace` is the real meal-delivery address book (Home/Office/…), with optional lat/lng, soft cap `MAX_ACTIVE_DELIVERY_PLACES = 10` in `delivery_place.py`, and lunch/dinner mapping via `MealDeliveryPreference` / `MealDeliveryDayOverride`. Identity addresses (`CustomerAddress` present/permanent) stay separate.
3. **Admin settings pattern**: Singleton DB models with `pk=1` and `.load()` (e.g. `OrderWalletSettings`, `MealOffSettings`) — not django-constance.

Stakeholders: React website + Flutter Android (Token auth), guests with opaque `guest_session_id` / `X-Guest-Session-Id`, admins tuning location policy, and ops relying on existing place → `OrderDelivery` snapshots.

Constraints: reuse delivery places (no second address book); keep check API backward compatible; never auto-mutate lunch/dinner defaults on location save; business logic in services; thin views.

## Goals / Non-Goals

**Goals:**
- Persist GPS/map/manual/guest-migration locations as normal `CustomerDeliveryPlace` rows with source metadata.
- Track **last detected** GPS separately from **saved delivery place** on `CustomerLocationPreference` for UX + analytics.
- Clear customer APIs: get preference, refresh detected location, save-as-place.
- Admin-configurable duplicate radius, max places, and refresh interval.
- Duplicate checks on create and geo-update with **self-exclusion**.
- Soft accuracy warnings reused from service-area threshold.
- Guest → login offer with `location_source=guest_migration`.
- Client docs for permission-denied and explicit meal-default opt-in UX.
- Additive check-response hints + tests.

**Non-Goals:**
- Server-side Nominatim/Google reverse geocoding in v1.
- Replacing `CustomerAddress` or changing meal preference resolution precedence.
- Auto-setting lunch/dinner when saving a location.
- New Hub model; guest permanent address book; JWT migration.
- Hard-rejecting low-accuracy GPS (warning only, same as service-area check).

## Decisions

### 1. Reuse `CustomerDeliveryPlace` as the only saved location store
- **Choice:** Extend `CustomerDeliveryPlace` with:
  - `location_source` — `gps` | `manual` | `map_pin` | `search` | `guest_migration` | `""` (legacy)
  - `location_accuracy` — nullable meters
  - `formatted_address` — optional (fallback: `full_address`)
  - `is_verified_location` — bool when coords validated from GPS/map/guest flows
  - Existing `latitude` / `longitude` remain coordinate fields.
- **Rationale:** Single address book already wired to preferences and order snapshots; `guest_migration` enables conversion analytics.
- **Alternatives considered:** Parallel location table — rejected. Overload `CustomerAddress` — rejected.

### 2. `CustomerLocationPreference`: detected ≠ saved
- **Choice:** OneToOne → `CustomerProfile` with:
  - `active_delivery_place` (FK nullable, `SET_NULL`) — saved delivery location pointer
  - `saved_latitude`, `saved_longitude`, optional `saved_location_name`, `saved_at` — denormalized from last save / linked place
  - `last_detected_latitude`, `last_detected_longitude`, optional `last_detected_location_name`, optional `last_detected_accuracy`, `detected_at` — last GPS/map detect even if user did **not** save
  - `is_active`
- **Rationale:** User at Home (saved Chawkbazar) who refreshes GPS at Office without saving must still show detected Office vs saved Chawkbazar separately; supports future analytics (detect without save).
- **Alternatives considered:** Single lat/lng on preference — collapses detected and saved. Only `ServiceAreaRequest` history — not a stable customer resource.

### 3. API naming for clear frontend flows
- **Choice** (under `/user_management/customer/`):
  - `GET location-preference/` — full preference: saved + detected + `can_refresh` / `expires_at` (based on `detected_at` + refresh interval)
  - `PATCH location-preference/refresh/` — body: detected coords, accuracy, location_name, source; updates **detected** fields + `detected_at` only; does **not** create a place
  - `POST location-preference/save-as-place/` — creates/updates a `CustomerDeliveryPlace` from current detected (or explicit body), updates saved fields + `saved_at` + optional `active_delivery_place`; optional explicit flags only (see Decision 4)
  - Guest offer remains a sibling action (e.g. `.../location-preference/guest-offer/`)
- **Rationale:** Matches product UX: refresh ≠ save.
- **Alternatives considered:** Single PATCH doing both — ambiguous for clients.

### 4. Never auto-change lunch/dinner defaults
- **Choice:** Saving a location / place MUST NOT mutate `MealDeliveryPreference` unless the client sends explicit opt-in flags after user confirmation, e.g. `set_as_default_delivery_place` and/or `set_lunch_default` / `set_dinner_default` (all default **false**). UI copy is client-owned (Save popup “default delivery?” and separate “update lunch/dinner?”).
- **Rationale:** Saving Office for map UX ≠ wanting meals delivered there.
- **Alternatives considered:** Auto-set when customer has no prefs — rejected (surprising). Single combined flag only — weaker than separate lunch/dinner options.

### 5. Duplicate detection excludes self on update
- **Choice:** On create, compare new coords to all other active places with coords. On geo-update, same check but **exclude** the place being updated (`public_id` / pk). Reject with `LOCATION_ALREADY_EXISTS` (422) when within `duplicate_radius_km`.
- **Rationale:** Editing Home coords must not collide with itself.
- **Alternatives considered:** Only check on create — allows accidental near-duplicates via edit to another place’s pin.

### 6. Accuracy soft warning (reuse existing threshold)
- **Choice:** When `accuracy` is present and `> SERVICE_AREA_ACCURACY_THRESHOLD_M` (default 500), location preference refresh / save-as-place / check responses include soft `warning_code=LOW_LOCATION_ACCURACY` (existing service-area code; same meaning as product’s “LOCATION_ACCURACY_LOW”). Operation still succeeds. Omitted accuracy (map pin) treated as reliable.
- **Rationale:** One threshold and one machine code across apps; urban/China GPS jitter is common.
- **Alternatives considered:** Hard reject — too aggressive. New code `LOCATION_ACCURACY_LOW` — duplicate vocabulary; prefer existing `LOW_LOCATION_ACCURACY`.

### 7. Admin settings singleton `CustomerLocationSettings`
- **Choice:** In `user_management`: `duplicate_radius_km` (0.5), `max_active_delivery_places` (3), `location_refresh_interval_hours` (24); Django admin + verified-admin web GET/PATCH. Accuracy threshold stays env (`SERVICE_AREA_ACCURACY_THRESHOLD_M`) unless later promoted.
- **Rationale:** Matches `OrderWalletSettings` pattern; accuracy already env-tuned for hubs.

### 8. Address limit & grandfathering
- **Choice:** Replace `MAX_ACTIVE_DELIVERY_PLACES` with settings; `ADDRESS_LIMIT_REACHED`; grandfather existing > limit (no delete).

### 9. Coordinate requirements
- **Choice:** Geo sources `{gps, map_pin, search, guest_migration}` require lat+lng and address text. Legacy text-only edits without coords remain allowed for places that already lack coords.

### 10. Guest handling
- **Choice:** Guests never get places. After auth, offer latest `ServiceAreaRequest` for `guest_session_id`. Accept → create place with `location_source=guest_migration`, update preference saved fields; subject to dupe/limit rules.

### 11. Refresh policy + permission-denied (client)
- **Choice:** Backend returns `can_refresh` / `expires_at` from `detected_at` (or documents fallback if only saved exists). Clients MUST: if OS location permission denied, show **saved** location (and last detected if any) and MUST NOT repeatedly prompt; only prompt on explicit user action or when `can_refresh` and permission already granted.
- **Rationale:** Backend cannot read OS permission; docs encode the rule.

### 12. Service-area check compatibility
- **Choice:** Additive `saved_location` for authenticated customers (`exists`, `address_id`, freshness). Existing fields unchanged. Existing accuracy warning unchanged.

### 13. `LocationService` abstraction
- **Choice:** Wrap Haversine, coordinate validation, accuracy reliability helper; pluggable reverse_geocode stub (v1 client-supplied names).

## Risks / Trade-offs

- [Default max 3 vs users with up to 10] → Grandfather; admin can raise limit.
- [Detected vs saved confusion in clients] → Document GET payload shape with both blocks; Flutter/React guides with examples.
- [Duplicate false positives] → Tunable radius; self-exclude on update.
- [Low accuracy still saved] → Soft warning only; clients may nudge user to retry.
- [Meal routing unchanged on save] → Explicit flags + docs; ops still depend on meal prefs separately.

## Migration Plan

1. Add place metadata fields + `guest_migration` source choice.
2. Create `CustomerLocationPreference` (detected + saved columns) and `CustomerLocationSettings`.
3. Wire services: limit, duplicate (exclude self), preference get/refresh/save-as-place, guest offer, accuracy warning helper.
4. APIs + OpenAPI; additive check `saved_location`.
5. Docs: permission-denied, meal-default opt-in, API call order.
6. Tests for all new behaviors; regression on check + meal resolution.
7. Rollback: additive; reverse migration if unused.

## Open Questions

- Exact admin settings URL mount (user_management web vs `/api/v1/web/`) — follow nearest existing pattern at implement time.
- Bangla vs English API `message` — keep English + stable `error_code` / `warning_code`; clients localize.
