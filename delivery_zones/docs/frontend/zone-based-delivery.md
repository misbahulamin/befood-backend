# Zone-based delivery management (frontend)

## Summary

Manual operational routing: **Zone → Location → Sub-location → Customer**, with one primary Delivery Man per zone. Street addresses (`CustomerDeliveryPlace`) stay unchanged. Customer location and zone are always **derived** from the assigned sub-location—moving a location or sub-location cascades automatically.

## Auth

All admin endpoints: `Authorization: Token <admin_token>` + verified admin.  
Deliveryman board: verified Delivery Man token.

## Compatibility (Bridge → Contract)

| Phase | Backend flag | FE behavior |
|-------|--------------|------------|
| **Bridge** (default) | `DELIVERY_SUB_LOCATION_LEGACY_LOCATION_ASSIGN=True` | Prefer `delivery_sub_location_public_id`; may still send `delivery_location_public_id` (maps to default sub) |
| **Contract** | flag `False` | **Must** send `delivery_sub_location_public_id`; location-only assign returns 422 |

Deploy order: backend Expand+Bridge → FE dual-aware release → flip Contract flag outside peak meal times.

## Admin — Zones

Base: `/api/v1/web/delivery-zones/`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | List zones (`status`, `q`, pagination); includes `location_count`, `sub_location_count` |
| POST | `/` | Create zone |
| GET/PATCH/DELETE | `/{public_id}/` | Detail / update / delete if empty |
| PATCH | `/{public_id}/assign-delivery-man/` | Set or clear primary rider (`delivery_man_public_id`) |
| PATCH | `/{public_id}/locations/reorder/` | Dense 1..n location priorities |
| POST | `/{public_id}/deactivate/` | Soft-deactivate |
| GET | `/ops/summary/?service_date=&meal_period=` | Counts + workload (zone → location → sub-location) — **one day / meal** |
| GET | `/analytics/matrix/?from=&to=` | Period geo analytics matrix + rankings — see [delivery-geo-analytics.md](./delivery-geo-analytics.md) |

**Create example**

```json
POST /api/v1/web/delivery-zones/
{
  "name": "Zone 1",
  "code": "zone-1",
  "priority": 1,
  "delivery_man_public_id": null
}
```

## Admin — Locations

Base: `/api/v1/web/delivery-locations/`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | List (`zone_public_id`, `status`, `q`); includes `sub_location_count` |
| POST | `/` | Create in a zone (also creates default sub-location) |
| GET/PATCH/DELETE | `/{public_id}/` | Detail / update (incl. move zone) / delete if empty |
| PATCH | `/{public_id}/sub-locations/reorder/` | Dense 1..n sub-location priorities |

**Move location (cascade customers)**

```json
PATCH /api/v1/web/delivery-locations/{public_id}/
{ "zone_public_id": "<zone-2-public-id>" }
```

No per-customer update is required after a move.

## Admin — Sub-locations

Base: `/api/v1/web/delivery-sub-locations/`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | List (`location_public_id`, `zone_public_id`, `status`, `q`) |
| POST | `/` | Create under a location |
| GET/PATCH/DELETE | `/{public_id}/` | Detail / update (incl. move location) / delete if no customers |

**Create example**

```json
POST /api/v1/web/delivery-sub-locations/
{
  "name": "Gate A",
  "location_public_id": "<chawkbazar-public-id>",
  "priority": 2,
  "status": "active"
}
```

**201 response (shape)** includes `public_id`, `name`, `priority`, `status`, `is_default`, nested `location` and `zone` summaries, `customer_count`.

**Reorder**

```json
PATCH /api/v1/web/delivery-locations/{location_public_id}/sub-locations/reorder/
{
  "sub_locations": [
    { "public_id": "<gate-a>", "priority": 1 },
    { "public_id": "<gate-b>", "priority": 2 }
  ]
}
```

Must include every sub-location under that location with dense priorities `1..n`.

## Admin — Customer assignment

Primary (Bridge + Contract):

```http
PATCH /api/v1/web/customers/{customer_public_id}/delivery-location/
{ "delivery_sub_location_public_id": "<sub-location-public-id>" }
```

Clear: `{ "delivery_sub_location_public_id": null }`

Legacy (Bridge only):

```json
{ "delivery_location_public_id": "<location-public-id>" }
```

Maps to that location’s **default** sub-location.

**Response**

```json
{
  "delivery_sub_location": { "public_id": "...", "name": "Gate A", "priority": 2, "status": "active", "is_default": false },
  "delivery_location": { "public_id": "...", "name": "Chawkbazar", "priority": 1, "status": "active" },
  "delivery_zone": { "public_id": "...", "name": "Zone 1", "code": "zone-1", "priority": 1, "status": "active" }
}
```

Customer list/detail include `delivery_sub_location`, derived `delivery_location`, and derived `delivery_zone`.  
List filters: `zone_public_id`, `location_public_id`, `sub_location_public_id`, `has_delivery_location`, `has_delivery_sub_location`.

## Admin — Deliveryman zone binding

```http
PATCH /user_management/admin/deliverymen/{public_id}/assign-zone/
{ "zone_public_id": "<zone-public-id>" }
```

Clear with `null`. A rider can be primary on only one zone. Only approved/verified riders can be assigned.

Deliveryman list/detail include `assigned_zone`.

## Admin — Today board filters

Existing `/api/v1/web/orders/today-board/` gains optional:

- `zone_public_id`
- `location_public_id`
- `sub_location_public_id`
- `delivery_man_public_id`

## Admin — Ops summary fields

`GET /api/v1/web/delivery-zones/ops/summary/?service_date=YYYY-MM-DD&meal_period=lunch`

- `unassigned_sub_location_count` (and alias `unassigned_location_count`) — deliveries whose customer has no sub-location
- `zones[].locations[].sub_locations[]` — each with `counts` (`scheduled` / `delivered` / `skipped` / `missed` / `total`)
- `delivery_man_workload[]`

## Delivery Man — Today board

```http
GET /user_management/deliveryman/deliveries/today-board/
Authorization: Token <deliveryman_token>
```

**BREAKING:** The board always returns **business today** and the **single active meal period** from meal-off settings (`Asia/Dhaka`). Client `service_date` and `meal_period` query params are **ignored**. Lunch and dinner are never returned together.

Active window (`get_current_delivery_period`):

| Local time | Active period |
|------------|---------------|
| `<= lunch_off_time` | none (empty board; overnight until lunch opens — not prior dinner) |
| after lunch_off through dinner_off | `lunch` |
| after dinner_off | `dinner` |

Optional query params for list filtering:

| Param | Behavior |
|-------|----------|
| `status=scheduled` | To Deliver only (same as default) |
| `status=delivered` | Delivered tab only |
| `status=all` | Scheduled + delivered |
| `include_delivered=true` | Legacy: scheduled + delivered when `status` omitted |
| `service_date` / `meal_period` / `zone_public_id` | Ignored |

Foreign `zone_public_id` is ignored—board is always the rider’s assigned zone. No zone → empty periods + message.

**Cooking eligibility (low-balance meal-stop):** Customers with `meal_service_blocked_low_balance=true` are omitted. Customers without an active sub-location are also omitted.

**Example response shape (nested sub-locations)**

```json
{
  "service_date": "2026-09-18",
  "active_meal_period": "lunch",
  "timezone": "Asia/Dhaka",
  "total_count": 25,
  "zone": { "public_id": "...", "name": "Zone 1", "code": "zone-1", "priority": 1 },
  "periods": {
    "lunch": {
      "total_count": 25,
      "locations": [
        {
          "location_public_id": "...",
          "location_name": "Chawkbazar",
          "location_priority": 1,
          "delivery_count": 10,
          "sub_locations": [
            {
              "sub_location_public_id": "...",
              "sub_location_name": "Gate A",
              "sub_location_priority": 1,
              "delivery_count": 6,
              "customers": [
                {
                  "delivery_public_id": "...",
                  "customer_name": "Rahim",
                  "customer_phone": "1713000001",
                  "full_address": "...",
                  "location_name": "Chawkbazar",
                  "location_priority": 1,
                  "sub_location_name": "Gate A",
                  "sub_location_priority": 1,
                  "meal_period": "lunch",
                  "meal_name": "Student Package",
                  "package_name": "Student Package",
                  "package_public_id": "...",
                  "meal_quantity": 1,
                  "notes": "",
                  "menu_items_label": "chicken + dhal + vat + vegetable",
                  "status": "scheduled",
                  "delivered_at": null,
                  "delivered_by_rider_public_id": null,
                  "delivered_by_name": null
                }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

## Delivery Man — Today summary

```http
GET /user_management/deliveryman/deliveries/today-summary/
Authorization: Token <deliveryman_token>
```

Stop-based KPIs for the same zone + active meal window as the board, plus dynamic package breakdown. See `docs/frontend/deliveryman-today-ops.md` for full mobile contract.

## Delivery Man — Mark delivered

```http
POST /user_management/deliveryman/deliveries/{delivery_public_id}/mark/
Authorization: Token <deliveryman_token>
Content-Type: application/json

{ "status": "delivered" }
```

- Delivery must belong to the rider’s assigned zone (else 403).
- Reuses the same `mark_delivery` / wallet charge path as admin + cron (`meal-delivery:{public_id}` idempotency).
- **Low-balance meal-stop:** if the customer has `meal_service_blocked_low_balance=true`, mark is rejected with **422** and `error_code: MEAL_SERVICE_BLOCKED_LOW_BALANCE`.
- Already delivered → 200 with same status (no second wallet debit).

## Cascade rule (UI copy)

> Moving a location to another zone (or a sub-location to another location) updates every assigned customer’s derived location/zone immediately. You do not need a bulk customer update.

## Admin Panel implementation plan (`/admin/delivery-zones`)

Target page: `http://127.0.0.1:5173/admin/delivery-zones` (Admin Panel repo — not this backend).

### Recommended UI tree

1. **Zone list** — create / edit / deactivate / assign Delivery Man / reorder locations
2. **Locations under selected zone** — create / edit / move zone / reorder
3. **Sub-locations panel/drawer under selected location** — name, priority, status, reorder, deactivate/delete
4. **Customer assign** (delivery-zones page and/or customer detail) — cascade selectors **Zone → Location → Sub-location**; submit `delivery_sub_location_public_id`

### Empty / error states

- Location with only the default sub-location: show default row; allow rename/split into Gate A/B
- Delete blocked (`SUB_LOCATION_HAS_CUSTOMERS` / `LOCATION_HAS_CUSTOMERS` / `LOCATION_HAS_SUB_LOCATIONS`): prompt reassign first
- Inactive parent: disable create/move into inactive location or zone
- Contract 422 on location-only assign: switch FE to sub-location field

### Concrete API call order (happy path)

1. `POST /api/v1/web/delivery-zones/` — create zone  
2. `POST /api/v1/web/delivery-locations/` — create location (default sub-location created server-side)  
3. `POST /api/v1/web/delivery-sub-locations/` — create Gate A / Gate B (optional; or rename default)  
4. `PATCH /api/v1/web/customers/{id}/delivery-location/` with `delivery_sub_location_public_id`  
5. Optional: `PATCH …/delivery-locations/{id}/sub-locations/reorder/` then verify rider board nesting  

### FE deploy recommendation

Ship FE after backend Bridge is live on staging/AWS. Keep reading both location and sub-location fields. Flip Contract flag only after FE confirms dual-aware assign is in production.

## Related docs

- Backend: [zone-based-delivery.md](../backend/zone-based-delivery.md)
- Admin customers: [admin-customer-management.md](../../user_management/docs/frontend/admin-customer-management.md)
- Deliveryman auth: [deliveryman-auth.md](../../user_management/docs/frontend/deliveryman-auth.md)
