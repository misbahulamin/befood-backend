# Zone-based delivery (backend)

## Purpose

Operational neighborhood grouping for meal delivery planning without GPS polygons yet.

Hierarchy: **Zone → Location → Sub-location → Customer**. Location and zone on a customer are always **derived** from the assigned sub-location.

**Do not confuse with:**

| Concept | App | Role |
|---------|-----|------|
| `delivery_zones.DeliveryZone` | `delivery_zones` | Manual ops zone + rider |
| `service_area.ServiceArea` | `service_area` | GPS coverage hub + radius |
| `business.DeliveryZone` | `business` | Unused fee circle scaffold |

## Models

### DeliveryZone

- `name`, unique `code`, `priority`, `status` (`active`/`inactive`)
- `assigned_delivery_man` → `RiderProfile` (nullable; unique when set)
- Future hooks: `centroid_*`, `boundary_geojson`, `external_map_place_id`, `geo_metadata`

### DeliveryLocation

- `name`, FK `zone`, `priority` (unique among active locations in zone), `status`
- Same future geo hooks
- Creating a location also creates one **default** sub-location (`name` = location name, `priority=1`, `is_default=True`)

### DeliverySubLocation

- `name`, FK `location` (`PROTECT`), `priority` (unique among active sub-locations in location), `status`
- `is_default` — at most one per location; used for legacy location-only assign mapping
- Same future geo hooks
- `public_id` exposed to API clients

### CustomerProfile

- `delivery_sub_location` — **source of truth** (nullable FK → `DeliverySubLocation`)
- `delivery_location` — mirrored parent during **Bridge** (kept in sync by assign service)
- Derived location = `sub.location`; derived zone = `sub.location.zone`

### OrderDelivery.logistics_sub_location

- Optional nullable snapshot set at rider completion; historical rows are not backfilled

## Expand–contract / Bridge flag

| Setting | Default | Meaning |
|---------|---------|---------|
| `DELIVERY_SUB_LOCATION_LEGACY_LOCATION_ASSIGN` | `True` | Bridge: accept `delivery_location_public_id` and map to that location’s default sub-location |

When the flag is `False` (Contract), location-only assign returns `422` / `LEGACY_LOCATION_ASSIGN_DISABLED`.

Data migration `delivery_zones.0003_backfill_default_sub_locations` creates one default sub-location per existing location and backfills every customer that had `delivery_location`.

## Services

| Module | Responsibility |
|--------|----------------|
| `services/zones.py` | CRUD, assign/clear rider, delete-if-empty |
| `services/locations.py` | CRUD, move zone, delete-if-empty (blocks if sub-location customers or remaining sub-locations) |
| `services/sub_locations.py` | CRUD, move location, deactivate, delete-if-empty |
| `services/priority.py` | Allocate / swap / reorder priorities (zone, location, sub-location) |
| `services/assignment.py` | Assign/clear sub-location; Bridge legacy location assign; hierarchy summaries |
| `services/board.py` | Deliveryman zone-scoped board grouped location → sub-location → customers |
| `services/today_summary.py` | Rider today metrics + package breakdown |
| `services/ops.py` | Admin summary with per-sub-location counts; unassigned = missing sub-location |
| `services/geo_analytics.py` | Period geo matrix + rankings (see [delivery-geo-analytics.md](./delivery-geo-analytics.md)) |
| `services/unassigned_digest.py` | Twice-daily admin email of active subscribers with null `delivery_sub_location` (see [unassigned-delivery-digest.md](./unassigned-delivery-digest.md)) |

## Mounted URLs

| Collection | Path |
|------------|------|
| Zones | `/api/v1/web/delivery-zones/` |
| Locations | `/api/v1/web/delivery-locations/` |
| Sub-locations | `/api/v1/web/delivery-sub-locations/` |
| Sub reorder | `PATCH /api/v1/web/delivery-locations/{public_id}/sub-locations/reorder/` |
| Customer assign | `PATCH /api/v1/web/customers/{public_id}/delivery-location/` |
| Ops summary | `GET /api/v1/web/delivery-zones/ops/summary/` |
| Geo analytics matrix | `GET /api/v1/web/delivery-zones/analytics/matrix/` |
| Deliveryman board | `GET /user_management/deliveryman/deliveries/today-board/` |
| Admin today board | `GET /api/v1/web/orders/today-board/` (`zone_public_id`, `location_public_id`, `sub_location_public_id`, `delivery_man_public_id`) |

## Cascade

Changing a sub-location’s parent location (or that location’s zone) immediately changes derived location/zone for all customers on that sub-location. No bulk customer write.

## Board scoping

`OrderDelivery` → `delivery_customer()` → `delivery_sub_location` → `location.zone` (Bridge falls back to `delivery_location.zone` only when sub is null). Inactive sub-locations/locations are excluded. Customers without a sub-location are omitted from the deliveryman board and counted in ops `unassigned_sub_location_count`.

Board payload nests `locations[].sub_locations[].customers[]`, ordered by location priority then sub-location priority.

### Deliveryman active-meal board

`build_deliveryman_board` uses `orders.services.meal_off.get_current_delivery_period()`:

- Returns at most one of `lunch` / `dinner` (never both).
- Before/at `lunch_off_time` → empty active window (not prior-day dinner).
- Client `service_date` / `meal_period` query params are ignored.
- Status filter (`resolve_board_statuses`):
  - default / `status=scheduled` → pending (To Deliver)
  - `status=delivered` → completed stops only
  - `status=all` → scheduled + delivered
  - legacy `include_delivered=true` (when `status` omitted) → scheduled + delivered
- Customer rows include additive `package_name` / `package_public_id`, `sub_location_name` / `sub_location_priority`, and for delivered rows `delivered_at` / `delivered_by_rider_public_id` / `delivered_by_name`.

### Deliveryman today summary

`build_deliveryman_today_summary` uses the same zone + meal-off period + low-balance exclusion as the board. Stop-based `total` / `delivered` / `pending` plus dynamic `packages[]` from subscription/order meal snapshots. Mounted at `GET /user_management/deliveryman/deliveries/today-summary/`.

**Low-balance meal-stop parity with kitchen:** `zone_scoped_deliveries` excludes customers with `meal_service_blocked_low_balance=true`.

### Deliveryman mark ↔ auto-delivery parity

Mark path: `POST /user_management/deliveryman/deliveries/{public_id}/mark/` → zone check → low-balance gate → `mark_delivery_and_notify`.

| Gate | Auto cron | Deliveryman mark | Admin mark |
|------|-----------|------------------|------------|
| Completion (`mark_delivery` + charge + Onahar/referral/FCM) | yes | yes | yes |
| Exclude `meal_service_blocked_low_balance` | yes (queryset) | yes (422 `MEAL_SERVICE_BLOCKED_LOW_BALANCE`) | **no** (ops override) |
| Zone membership | N/A | yes (403) | N/A |

Shared helper: `orders.services.meal_demand.low_balance_blocked_q` / `delivery_customer_is_meal_service_blocked`.

## Edge cases

- Delete zone blocked if locations remain
- Delete location blocked if customers remain on location/sub-locations, or if sub-locations still exist
- Delete sub-location blocked if customers remain
- Create under inactive location/zone rejected
- Assign inactive sub-location rejected
- Duplicate active priority in same location → `PRIORITY_CONFLICT`
- Same rider on two zones → `409` / `DELIVERY_MAN_ALREADY_ASSIGNED`
- Non-approved rider → `DELIVERY_MAN_NOT_APPROVED`
- Legacy location assign with flag off → `LEGACY_LOCATION_ASSIGN_DISABLED`

## Future GPS

Keep using `resolve_operational_sub_location` / `resolve_operational_location`. Later implementations can match lat/lng to polygons without changing the Zone→Location→Sub-location hierarchy.
