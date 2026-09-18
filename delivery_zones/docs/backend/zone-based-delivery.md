# Zone-based delivery (backend)

## Purpose

Operational neighborhood grouping for meal delivery planning without GPS polygons yet.

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

### CustomerProfile.delivery_location

- Nullable FK → `DeliveryLocation`
- **Derived zone** = `customer.delivery_location.zone` (no customer.zone column)

## Services

| Module | Responsibility |
|--------|----------------|
| `services/zones.py` | CRUD, assign/clear rider, delete-if-empty |
| `services/locations.py` | CRUD, move zone, delete-if-empty |
| `services/priority.py` | Allocate / swap priorities safely |
| `services/assignment.py` | Customer location assign/clear |
| `services/ops.py` | Admin summary aggregation |
| `services/board.py` | Deliveryman zone-scoped board |

## Cascade

Changing `DeliveryLocation.zone_id` immediately changes derived zone for all customers with that FK. No bulk customer write.

## Board scoping

`OrderDelivery` → `delivery_customer()` → `delivery_location.zone`. Inactive locations are excluded from deliveryman boards. Unassigned customers appear only in admin `unassigned_location_count`.

### Deliveryman active-meal board

`build_deliveryman_board` uses `orders.services.meal_off.get_current_delivery_period()`:

- Returns at most one of `lunch` / `dinner` (never both).
- Before/at `lunch_off_time` → empty active window (not prior-day dinner).
- Client `service_date` / `meal_period` query params are ignored.

**Low-balance meal-stop parity with kitchen:** `zone_scoped_deliveries` excludes customers with `meal_service_blocked_low_balance=true` (same Q as `orders.services.meal_demand.low_balance_blocked_q` / auto-delivery). Kitchen `today-meal-requirement` and `today-order-details` already omit those customers from cooking; the rider board must not list them either. Exclusion uses the block **flag**, not a live `Wallet.balance < meal_stop_threshold` recompute. Meal preferences may still be on; only board visibility changes. Optional kwarg `include_low_balance_blocked=True` exists for future diagnostic callers (deliveryman defaults to exclude).

### Deliveryman mark ↔ auto-delivery parity

Mark path: `POST /user_management/deliveryman/deliveries/{public_id}/mark/` → zone check → **same** low-balance meal-stop gate as `eligible_delivery_queryset` → `mark_delivery_and_notify` (wallet idempotency `meal-delivery:{public_id}`).

| Gate | Auto cron | Deliveryman mark | Admin mark |
|------|-----------|------------------|------------|
| Completion (`mark_delivery` + charge + Onahar/referral/FCM) | yes | yes | yes |
| Exclude `meal_service_blocked_low_balance` | yes (queryset) | yes (422 `MEAL_SERVICE_BLOCKED_LOW_BALANCE`) | **no** (ops override) |
| Zone membership | N/A | yes (403) | N/A |

Shared helper: `orders.services.meal_demand.low_balance_blocked_q` / `delivery_customer_is_meal_service_blocked`.

## Edge cases

- Delete zone blocked if locations remain
- Delete location blocked if customers remain
- Create/move into inactive zone rejected
- Assign inactive location rejected
- Same rider on two zones → `409` / `DELIVERY_MAN_ALREADY_ASSIGNED`
- Non-approved rider → `DELIVERY_MAN_NOT_APPROVED`

## Future GPS

Keep using `resolve_operational_location(customer)`. Later implementations can match lat/lng to location polygons without changing the Zone→Location hierarchy.
