# Customer location preference & GPS save (frontend / mobile)

## Summary

BeFood separates **last-detected GPS** from **saved delivery places**. Use the location-preference APIs so React and Flutter can:

1. Detect GPS once (`PATCH .../refresh/`)
2. Optionally save as a normal delivery place (`POST .../save-as-place/`)
3. Reuse saved location without re-prompting OS permission every visit
4. After guest → login, offer migrating the last guest check

**Important:** Saving a place does **not** change lunch/dinner defaults unless the user confirms and you send explicit flags (`false` by default).

Target clients: React website + Flutter Android (same Token APIs).

## Auth & base

```http
Authorization: Token <token>
```

Base: `/user_management/`

Guest checks (before login) still use:

```http
X-Guest-Session-Id: <uuid>
POST /api/v1/service-areas/check/
```

## Recommended call order

### Logged-in customer (happy path)

1. `GET /user_management/customer/location-preference/`
2. If `exists` and saved location present and OS permission is **denied** → show **saved** (and last detected if any); **do not** spam permission popups.
3. If permission already granted and `can_refresh` is true (or user taps Refresh) → get GPS → `PATCH .../location-preference/refresh/`.
4. Optionally `POST /api/v1/service-areas/check/` with the same coords (coverage).
5. If user taps **Save Location** → show confirmations:
   - Save as delivery address? (required for persist)
   - Make this default delivery location? → maps to flags below (optional)
   - Update lunch / dinner preference? → separate optional flags
6. `POST .../location-preference/save-as-place/`

### Guest → login migration

1. Guest: `POST /api/v1/service-areas/check/` with `X-Guest-Session-Id`
2. User logs in / registers (keep the same session id until the offer is resolved)
3. `GET .../location-preference/guest-offer/?guest_session_id=`
4. Show the confirmation popup **only** when `exists: true` and `status: "pending"`
5. Accept: `POST .../location-preference/guest-offer/` **or** decline: `POST .../location-preference/guest-offer/decline/` with `{ "guest_session_id": "..." }`
6. After accept **or** decline succeeds, **clear or rotate** the local guest session id so future anonymous checks start a fresh session

**Skip popup when GET returns `exists: false`.** Possible `status` values:

| status | Meaning |
|--------|---------|
| `pending` | Show offer (`exists: true`) |
| `accepted` | Already saved from this guest session |
| `declined` | User already dismissed |
| `suppressed` | Equivalent saved place / preference already exists |
| `none` | No guest history for this session |

Do **not** rely on in-memory or sessionStorage-only decline. Always call the decline API.

Login / `GET .../me/` may include additive:

```json
"location_confirmation": {
  "has_saved_location": true,
  "location_confirmed": true
}
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/user_management/customer/location-preference/` | Saved vs detected + freshness + confirmation flags |
| DELETE | `/user_management/customer/location-preference/` | Clear active saved preference (places kept; confirmation becomes false) |
| PATCH | `/user_management/customer/location-preference/refresh/` | Update **detected only** |
| POST | `/user_management/customer/location-preference/save-as-place/` | Create delivery place + update saved |
| POST | `/user_management/customer/location-preference/set-active-place/` | Point active saved at existing place `{ "place_id": "<uuid>" }` |
| GET | `/user_management/customer/location-preference/guest-offer/?guest_session_id=` | Offer after login |
| POST | `/user_management/customer/location-preference/guest-offer/` | Accept offer (`location_source=guest_migration`) |
| POST | `/user_management/customer/location-preference/guest-offer/decline/` | Decline offer (durable; no place created) |
| CRUD | `/user_management/customer/delivery-places/` | Address book (now with geo metadata) |

Admin:

| Method | Path |
|--------|------|
| GET/PATCH | `/user_management/admin/location-settings/` |
| GET/PATCH | `/api/v1/web/customers/location-settings/` |

## GET preference response

```json
{
  "exists": true,
  "is_active": true,
  "has_saved_location": true,
  "location_confirmed": true,
  "saved": {
    "exists": true,
    "address_id": "d906e339-95a9-42cf-a417-1d414767d14f",
    "latitude": "22.357825",
    "longitude": "91.846267",
    "location_name": "Chawkbazar, Chattogram",
    "saved_at": "2026-09-01T01:00:00Z"
  },
  "detected": {
    "exists": true,
    "latitude": "22.360100",
    "longitude": "91.850200",
    "location_name": "Agrabad",
    "accuracy": "18.00",
    "detected_at": "2026-09-01T08:00:00Z"
  },
  "can_refresh": false,
  "expires_at": "2026-09-02T08:00:00Z",
  "stale": false,
  "refresh_interval_hours": 24
}
```

`location_confirmed` / `has_saved_location` mean an **active saved** preference exists. They are unrelated to `is_verified_location` on a delivery place.

When nothing is set:

```json
{
  "exists": false,
  "has_saved_location": false,
  "location_confirmed": false
}
```

### Guest offer GET examples

Pending:

```json
{
  "exists": true,
  "status": "pending",
  "guest_session_id": "…",
  "latitude": "22.357825",
  "longitude": "91.846267",
  "location_name": "Chawkbazar",
  "formatted_address": "Chawkbazar, Chattogram",
  "is_serviceable": true
}
```

Already resolved / suppressed:

```json
{
  "exists": false,
  "status": "accepted",
  "guest_session_id": "…"
}
```

### Decline body

```json
{ "guest_session_id": "…" }
```

Response `200` with `exists: false` and `status: "declined"` (or the existing non-pending status if already resolved).

## PATCH refresh (detected only)

```json
{
  "latitude": "22.360100",
  "longitude": "91.850200",
  "accuracy": 187,
  "location_name": "Agrabad",
  "source": "gps"
}
```

Does **not** create a delivery place. Saved block stays unchanged.

If `accuracy` > `SERVICE_AREA_ACCURACY_THRESHOLD_M` (default 500), response may include:

```json
"warning_code": "LOW_LOCATION_ACCURACY"
```

Still HTTP 200.

## POST save-as-place

```json
{
  "label": "Current Location",
  "full_address": "Chawkbazar, Chattogram",
  "formatted_address": "Chawkbazar, Chattogram",
  "latitude": "22.357825",
  "longitude": "91.846267",
  "location_source": "gps",
  "location_accuracy": 12.5,
  "set_as_active": true,
  "set_as_default_delivery_place": false,
  "set_lunch_default": false,
  "set_dinner_default": false
}
```

If lat/lng omitted, backend uses last-detected coords from preference.

**UI rules for flags (all default false):**

| Popup | Flag |
|-------|------|
| “এই location টি default delivery location করবেন?” Yes | `set_as_default_delivery_place: true` (sets both lunch+dinner) |
| Update lunch only | `set_lunch_default: true` |
| Update dinner only | `set_dinner_default: true` |

Never set these true without an explicit user tap.

Response `201` includes preference payload plus nested `place`.

## Delivery place geo fields

On create/update of `/customer/delivery-places/`:

| Field | Notes |
|-------|--------|
| `location_source` | `gps` \| `manual` \| `map_pin` \| `search` \| `guest_migration` |
| `location_accuracy` | meters, optional |
| `formatted_address` | optional; can satisfy address text with `full_address` |
| `is_verified_location` | set true for geo sources with valid coords |
| `latitude` / `longitude` | required for geo sources |

## Error codes

| HTTP | error_code | When |
|------|------------|------|
| 422 | `LOCATION_ALREADY_EXISTS` | New/updated coords within admin duplicate radius of **another** place (self excluded on update) |
| 422 | `ADDRESS_LIMIT_REACHED` | Active places ≥ admin max (default 3) |
| 409 | `GUEST_OFFER_ALREADY_RESOLVED` | Accept attempted after offer already accepted/declined |
| 422 | `LOW_LOCATION_ACCURACY` | Soft warning on refresh/save (also returned as `warning_code` on success) |

Envelope:

```json
{
  "success": false,
  "message": "A delivery address already exists near this location.",
  "errors": {},
  "error_code": "LOCATION_ALREADY_EXISTS"
}
```

## Permission-denied UX (client-owned)

If OS location permission is **denied**:

1. Show `saved` location from GET preference (and last `detected` if present).
2. Do **not** repeatedly open the system permission dialog.
3. Offer a single “Enable location” affordance that opens app settings / explicit user action only.
4. Use `can_refresh` / `expires_at` only when permission is already granted.

## Admin settings (defaults)

| Key | Default | Effect |
|-----|---------|--------|
| `duplicate_radius_km` | 0.5 | Near-duplicate rejection |
| `max_active_delivery_places` | 3 | Soft create cap (grandfather existing) |
| `location_refresh_interval_hours` | 24 | Freshness / `can_refresh` |
| Env `SERVICE_AREA_ACCURACY_THRESHOLD_M` | 500 | Soft accuracy warning |

## Service-area check additive field

Authenticated check may include:

```json
"saved_location": {
  "exists": true,
  "address_id": "<place public_id>",
  "stale": false
}
```

Guests omit this or have no saved place. Existing check fields are unchanged.

## Related docs

- `user_management/docs/frontend/meal-delivery-addresses.md` — lunch/dinner prefs
- `service_area/docs/frontend/customer-service-area.md` — coverage check
