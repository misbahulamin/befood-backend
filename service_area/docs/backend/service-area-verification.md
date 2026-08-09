# Service Area Verification (Backend)

## Quick summary

BeFood decides **serviceability from geographic distance**, not from customer area-name strings. Admins manage hub points with a radius (km). Customers/guests send browser/device latitude & longitude to `POST /api/v1/service-areas/check/`. Checkout re-validates delivery-place coordinates against **active** hubs.

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| POST | `/api/v1/service-areas/check/` | Guest or customer | Coverage check + history |
| POST | `/api/v1/service-areas/demand/` | Guest or customer | “Want BeFood here” demand row |
| GET/POST | `/api/v1/web/service-areas/` | Verified admin | List / create hubs |
| GET/PATCH/DELETE | `/api/v1/web/service-areas/{public_id}/` | Verified admin | Retrieve / update / soft-delete |
| POST | `/api/v1/web/service-areas/{public_id}/status/` | Verified admin | Activate / deactivate |
| GET | `/api/v1/web/service-areas/requests/` | Verified admin | Paginated history |
| GET | `/api/v1/web/service-areas/requests/summary/` | Verified admin | Top areas analytics |

## Permissions

| Endpoint group | Auth |
|----------------|------|
| check / demand | `AllowAny` (optional Token attaches `customer_profile`) |
| `/api/v1/web/service-areas/*` | `IsVerifiedAdmin` |

Guest identity: body `guest_session_id` or header `X-Guest-Session-Id`.

**Never use IP geolocation** for matching. Only request-body coordinates.

## Models

### `ServiceArea`

- `public_id`, `name`, `latitude`, `longitude`, `radius_km`, `is_active`, `description`, `created_by`, timestamps

### `ServiceAreaRequest`

- Actor: `customer_profile` and/or `guest_session_id`
- Location: `latitude`, `longitude`, `accuracy`, `detected_location_name`, `formatted_address`
- Result: `matched_service_area` (nearest covering **or** nearest overall), `distance_km`, `is_serviceable`
- `request_kind`: `check` | `demand`

## Matching rules

1. Load **active** hubs only.
2. Haversine distance (km) from customer → each hub.
3. Covering set: `distance_km <= radius_km`.
4. If covering non-empty → nearest covering = `matched_service_area`, `service_available=true`.
5. Else → `nearest_service_area` = nearest hub, `service_available=false`.
6. Customer `location_name` is **display/analytics only**.

## Accuracy

Setting: `SERVICE_AREA_ACCURACY_THRESHOLD_M` (default `500`).

If `accuracy` is present and greater than threshold → `location_reliable=false`, `warning_code=LOW_LOCATION_ACCURACY`. History and distance still computed. Omitted accuracy (map pin) is treated as reliable.

## Check request / response

```http
POST /api/v1/service-areas/check/
Content-Type: application/json
X-Guest-Session-Id: optional-uuid
```

```json
{
  "latitude": 22.3569,
  "longitude": 91.7832,
  "accuracy": 18,
  "location_name": "GEC Circle, Chattogram"
}
```

Success (`200`):

```json
{
  "verified": true,
  "service_available": true,
  "location_reliable": true,
  "warning_code": null,
  "customer_location": {
    "latitude": "22.356900",
    "longitude": "91.783200",
    "accuracy": "18.00",
    "location_name": "GEC Circle, Chattogram"
  },
  "matched_service_area": {
    "public_id": "...",
    "name": "Chawkbazar Hub",
    "latitude": "22.340100",
    "longitude": "91.830100",
    "radius_km": "5.00"
  },
  "nearest_service_area": null,
  "distance_km": "3.8000"
}
```

Unavailable responses set `service_available=false` and fill `nearest_service_area` instead of `matched_service_area`.

## Demand

Same body as check → `POST /api/v1/service-areas/demand/`. Stores `request_kind=demand`. Does **not** unlock ordering.

## Checkout gate

Setting: `SERVICE_AREA_ORDER_GATE_ENABLED` (default `True`; disabled automatically during `manage.py test` on local settings).

On `create_meal_order`, after wallet/menu checks:

1. Collect lunch/dinner delivery places for the meal period (defaults + day overrides + fallback).
2. Require latitude/longitude on each place.
3. `assert_serviceable` against current active hubs.
4. Reject with `ServiceAreaOrderError`:
   - `DELIVERY_LOCATION_REQUIRED`
   - `SERVICE_AREA_UNAVAILABLE`

Client “already verified” flags are ignored.

## Error envelope (admin / service errors)

```json
{
  "success": false,
  "message": "...",
  "errors": {},
  "error_code": "UNSUPPORTED_FILTER"
}
```

## How to verify

```bash
python manage.py test service_area.tests.test_service_area
```

1. Create a hub via admin API.
2. POST check with coords inside radius → `service_available=true`.
3. POST check outside → nearest hub + false.
4. Deactivate hub → prior covering point becomes unavailable.
5. With gate enabled, create order with place outside hub → rejected.

## Production release checklist

Use this when shipping `service_area` to Render (or any host). The feature is a no-op on production until these steps land.

### Release contents (must ship together)

- Entire `service_area/` app (models, migrations, API, services, tests, docs)
- `core/urls.py` mounts:
  - `api/v1/service-areas/` → `service_area.api.urls`
  - `api/v1/web/service-areas/` → `service_area.api.web_urls`
- `core/settings/base.py`: `service_area` in `INSTALLED_APPS`, plus:
  - `SERVICE_AREA_ORDER_GATE_ENABLED` (default `True`)
  - `SERVICE_AREA_ACCURACY_THRESHOLD_M` (default `500`)
- `core/settings/local.py`: gate off under `manage.py test`
- `orders/services/order_service.py` + `orders/api/serializers.py`: checkout gate + `error_code`

Do **not** commit `db.sqlite3`, `__pycache__`, or secrets.

### Deploy steps

1. Commit + push the release contents above.
2. Wait for host deploy to finish.
3. Run migrations: `python manage.py migrate` (applies `service_area.0001_initial`).
4. Set env for cutover window: `SERVICE_AREA_ORDER_GATE_ENABLED=False`.
5. Smoke (must **not** be Django unmatched-route HTML 404):
   - `GET /api/v1/web/service-areas/` → 401/403 without admin token is OK
   - `POST /api/v1/service-areas/check/` with `{"latitude":22.35,"longitude":91.83}` → 200/422 JSON is OK
6. As verified admin, create ≥1 **active** hub.
7. Re-check in-radius / out-of-radius customer points.
8. Confirm admin `.../requests/` and `.../requests/summary/` resolve.
9. When delivery-place lat/lng UX is live, set `SERVICE_AREA_ORDER_GATE_ENABLED=True`.
10. Verify order create: in-radius OK; missing coords → `DELIVERY_LOCATION_REQUIRED`; outside → `SERVICE_AREA_UNAVAILABLE`.

### Rollback

If checkout regresses after enabling the gate:

1. Immediately set Render env `SERVICE_AREA_ORDER_GATE_ENABLED=False` and restart if needed.
2. Optionally redeploy the previous git revision (tables may remain; safe).
3. Do **not** drop `service_area` tables during an emergency rollback.

### Cutover handoff record

Fill after production cutover:

| Field | Value |
|-------|-------|
| Deploy commit SHA | |
| Migration applied (`service_area.0001_initial`) | yes / no |
| First hub `public_id` | |
| Gate enabled at (UTC) | |
| Operator | |
