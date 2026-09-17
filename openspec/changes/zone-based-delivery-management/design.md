## Context

BeFood runs lunch/dinner meal delivery via `OrderDelivery` slots (`orders`), customer street destinations via `CustomerDeliveryPlace` + meal preferences (`user_management`), and GPS coverage hubs via `ServiceArea` (`service_area`). Delivery Man accounts exist as `RiderProfile` with `DELIVERY_MAN` group and admin approval.

What is missing is an **operational routing hierarchy**: named neighborhoods (Locations) grouped into Zones, each Zone with a Delivery Man and priority for planning. Existing `business.DeliveryZone` is an unused outlet fee circle; `delivery.DeliveryAssignment` is scaffolding wired to whole `Order` rows and **not mounted** in `core/urls.py`. Neither should be revived as the operational Zone model.

Stakeholders: Admin Panel (zone/location/customer assignment + workload), Delivery Man app (zone-scoped today board), operations planners. Customers do not manage zones; they keep GPS address book as today.

Constraints: thin views + `services/`; `public_id` on new resources; web admin under `/api/v1/web/...`; money/GPS coverage gates unchanged; no company/branch tenancy.

## Goals / Non-Goals

**Goals:**

- Persist Zone → Location → Customer hierarchy with priorities for zone and location.
- Derive customer Zone solely from assigned Location (cascade on location zone move).
- Assign one primary Delivery Man per Zone (phase 1); scope deliveryman board to that zone.
- Admin CRUD for zones/locations; assign customer location; assign deliveryman zone.
- Admin ops: zone/location delivery counts and deliveryman workload for `service_date` + `meal_period`.
- Deliveryman lunch/dinner board: totals, customers grouped by location priority, address + location name.
- Schema hooks for future GPS polygons, multi-rider, auto-assignment.

**Non-Goals:**

- Google Maps / GPS auto zone detection / route optimization.
- Multiple simultaneous Delivery Men per zone (schema may allow later; API enforces one primary now).
- Replacing `ServiceArea` coverage verification or meal-order gates.
- Rewriting `CustomerDeliveryPlace` into Locations (street address stays separate from operational Location).
- Building Admin Panel / Deliveryman React UIs in this repo (API + docs only).
- Using `business.DeliveryZone` or unfinished `delivery.DeliveryAssignment` as the source of truth.

## Decisions

### 1. New Django app `delivery_zones` (not reuse ServiceArea / DeliveryZone)

- **Choice:** Create `delivery_zones` with models `DeliveryZone` and `DeliveryLocation`, services, web APIs, tests, docs.
- **Why:** Clear bounded context; avoids naming collision with `ServiceArea` (coverage) and `business.DeliveryZone` (fee). Keeps `orders` and `user_management` focused.
- **Alternatives:** Extend `service_area` — conflates GPS hubs with manual neighborhoods. Put models in `orders` — couples routing ops to meal slots. Revive `delivery` app models as-is — wrong parent (`Order` vs `OrderDelivery`) and unused routes.

### 2. Naming: API `delivery-zones` / `delivery-locations`; ORM `DeliveryZone` / `DeliveryLocation`

- **Choice:** Prefix with `Delivery` in ORM to avoid clash with any future geo Zone; JSON uses `zone` / `location` nested objects with `public_id`.
- **Why:** Matches project kebab URL + PublicIdMixin conventions.

### 3. Customer assignment lives on `CustomerProfile`, not on `CustomerDeliveryPlace`

- **Choice:** Add nullable FK `CustomerProfile.delivery_location` → `DeliveryLocation` (`SET_NULL` on location delete after guard). Derived zone = `customer.delivery_location.zone`.
- **Why:** Product hierarchy is Customer → Location → Zone. A customer may have multiple street places (home/office) but one operational neighborhood for routing in phase 1.
- **Alternatives:** FK on each `CustomerDeliveryPlace` — more accurate for multi-destination days later, but overbuilds phase 1 and breaks the stated “one location assignment” UX. Direct `customer.zone` FK — duplicates truth and breaks cascade-on-location-move.

### 4. Cascade rule: Location move updates Zone membership with zero customer row updates

- **Choice:** Customer has only `delivery_location_id`. Changing `DeliveryLocation.zone_id` immediately changes derived zone for all assigned customers. No bulk customer update job.
- **Why:** Matches product requirement exactly; single source of truth.
- **Implementation note:** Board queries join `OrderDelivery` → customer → `delivery_location` → zone; never denormalize zone onto customer unless a later performance phase needs a cached column (then keep it updated via signals/services — not phase 1).

### 5. Zone ↔ Delivery Man: FK on Zone (primary rider), optional reverse on RiderProfile

- **Choice:** `DeliveryZone.assigned_delivery_man` → `RiderProfile` (nullable, `SET_NULL`). Unique constraint: one zone per rider for phase 1 (`RiderProfile` may have at most one assigned zone via unique on zone FK or explicit unique on rider when set).
- **Why:** Product example is 1:1. Unique rider assignment prevents two zones claiming the same man.
- **Future:** Junction table `DeliveryZoneRider` with `is_primary` + workload weight; keep `assigned_delivery_man` as denormalized primary or migrate to junction.

### 6. Priorities are positive integers, unique per parent scope

- **Choice:** Zone `priority` unique among **active** zones (or globally unique among all zones — prefer unique among active). Location `priority` unique within the same zone among active locations. Lower number = deliver first / closer.
- **Why:** Matches “Priority 1 = closest.” Admin can reorder via update.
- **API:** Support optional `reorder` endpoint or accept priority swaps in service (transactional) to avoid uniqueness conflicts during edits.

### 7. Soft status over hard delete

- **Choice:** `status` ∈ `{active, inactive}` on Zone and Location. Delete (or deactivate) blocked when active customers are assigned, or force reassignment first. Hard delete only when empty and inactive (admin explicit).
- **Why:** Preserves historical board readability; avoids orphaning customers silently.

### 8. Deliveryman board queries `OrderDelivery`, scoped by customer location → zone

- **Choice:** For authenticated Delivery Man, resolve `RiderProfile` → assigned `DeliveryZone`. List `OrderDelivery` where `service_date` / `meal_period` match, status in scheduled (and optionally delivered), and `customer.delivery_location.zone_id = assigned zone`. Group response by `location.priority` then customer name.
- **Why:** Operational truth is daily slots, not monthly `Order`. Reuses address snapshots already on `OrderDelivery`.
- **Edge:** Customers without `delivery_location` do **not** appear on any deliveryman board; admin ops MUST surface an “unassigned location” count.

### 9. Street address vs operational Location

- **Choice:** Board shows `delivery_*_snapshot` (and/or live place) for address, plus `location.name` for operational neighborhood. No requirement that snapshot `area` string equals Location name.
- **Why:** GPS address book remains authoritative for where to knock; Location is for routing batches.

### 10. Admin ops aggregation endpoint

- **Choice:** `GET /api/v1/web/delivery-zones/ops/summary/?service_date=&meal_period=` returning per-zone counts, per-location counts, per-deliveryman workload (scheduled/delivered/skipped), plus unassigned-customer delivery count.
- **Why:** Single round-trip for admin planning dashboard.

### 11. API surface (phase 1)

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| CRUD | `/api/v1/web/delivery-zones/` | Admin | Zone manage + assign deliveryman |
| CRUD | `/api/v1/web/delivery-locations/` | Admin | Location manage + move zone + priority |
| PATCH | `/api/v1/web/customers/{public_id}/` or nested assign | Admin | Set `delivery_location_public_id` |
| GET | `/api/v1/web/delivery-zones/ops/summary/` | Admin | Counts + workload |
| PATCH | admin deliveryman detail | Admin | Assign/clear zone (or via zone update) |
| GET | `/user_management/deliveryman/deliveries/today-board/` (or `/api/v1/...`) | Deliveryman | Zone-scoped lunch/dinner board |

Auth: `IsVerifiedAdmin` / `IsVerifiedDeliveryman`. Resources use `public_id`.

### 12. Integration with existing today-board

- **Choice:** Extend admin today-board filters with optional `zone_public_id`, `location_public_id`, `delivery_man_public_id`. Do not break existing filters.
- **Why:** Kitchen/admin already use today-board; additive filters satisfy modified `admin-order-management` without a parallel list.

### 13. Future scalability hooks (nullable / unused now)

On `DeliveryLocation` / `DeliveryZone` reserve nullable fields or JSON `geo_metadata`:
- `centroid_latitude` / `centroid_longitude`
- `boundary_geojson` (Text/JSON)
- `external_map_place_id`
On assignment path, keep a single service `resolve_operational_location(customer)` that today returns FK and later can GPS-match.

### 14. Module layout

```text
delivery_zones/
  models.py
  services/zones.py, locations.py, assignment.py, board.py, ops.py
  api/web_views.py, serializers.py, openapi.py, web_urls.py
  tests/
  docs/frontend/ docs/backend/
```

Register in `INSTALLED_APPS` and mount under `core/urls.py` → `/api/v1/web/`.

## Risks / Trade-offs

- **[Risk] Confusion with ServiceArea / business.DeliveryZone** → Mitigation: docs + naming `DeliveryZone` in `delivery_zones` app; never use fee zone for ops.
- **[Risk] Customers without location invisible to riders** → Mitigation: admin unassigned count + blocklist or warning on subscription ops (optional soft warning only in phase 1).
- **[Risk] Priority uniqueness conflicts on reorder** → Mitigation: transactional swap/reorder service.
- **[Risk] One rider per zone too rigid** → Mitigation: unique constraint documented as phase-1; junction table planned.
- **[Risk] Lunch vs dinner places differ but one operational location** → Mitigation: accept for phase 1; future per-place location FK.
- **[Risk] Snapshot address stale vs profile** → Mitigation: existing snapshot behavior unchanged; board may also expose current place label when useful.
- **[Trade-off] New app vs stuffing into orders** → Extra app wiring; clearer long-term boundary.

## Migration Plan

1. Add `delivery_zones` app + models (`DeliveryZone`, `DeliveryLocation`) with indexes on `(zone, priority)`, `(status)`, `code` unique.
2. Add `CustomerProfile.delivery_location` FK (nullable) + migration.
3. Add unique assignment semantics for `DeliveryZone.assigned_delivery_man`.
4. Deploy APIs behind admin auth; seed zones/locations via admin UI (no mandatory data backfill).
5. Ops assigns existing customers to locations gradually; deliveryman boards populate as assignments complete.
6. Extend admin today-board filters + deliveryman board endpoint.
7. Rollback: deactivate feature flags not required; nullable FK means rollback of app code leaves column harmless; reverse migration only if no production dependency.

## Open Questions

- Exact deliveryman URL prefix: keep under `/user_management/deliveryman/...` vs new `/api/v1/deliveryman/...` — **default:** `/user_management/deliveryman/...` for consistency with existing deliveryman auth.
- Whether inactive locations hide customers from boards (yes) or still show with badge (prefer hide + admin unassigned/inactive report).
- Whether zone priority participates in multi-zone city sequencing for a single rider (N/A while 1 rider = 1 zone).
- Admin UI ownership lives in separate frontend repo — backend ships contracts in `docs/frontend/` only.
