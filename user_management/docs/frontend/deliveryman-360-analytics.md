# Delivery Man 360 Analytics (Frontend)

## Navigation

```text
Admin Panel
  → Delivery Men          (list with today / month / lifetime counts)
      → Select rider
          → Delivery Man Profile / 360 Analytics Dashboard
```

Identify riders by `public_id` (UUID). All analytics calls require verified-admin JWT/Token and typically `X-Client-Type: web`.

## Data-loading strategy

| UI section | When to load | API |
|------------|--------------|-----|
| Overview card + Today / Month / Lifetime | On page open | `GET /api/v1/web/delivery-men/{public_id}/` |
| Delivery history | History tab | `GET .../deliveries/` |
| Activity timeline | Timeline tab | `GET .../timeline/` |
| Route map | Route tab | `GET .../route/?service_date=&meal_period=` |
| Ranking / compare | Rankings page or drawer | `GET /api/v1/web/delivery-men/rankings/` |

**Do not** expect history rows inside the overview response. Lazy-load tabs (same pattern as Customer 360).

## Overview fields

| UI label | JSON path |
|----------|-----------|
| Name | `name` |
| Phone | `phone` |
| Assigned zone | `assigned_zone.name` / `code` |
| Joining date | `joining_date` |
| Status | `status` (`approval_status`) + `is_verified` |
| Availability | `is_available` |
| Today lunch/dinner/total | `today.lunch` / `dinner` / `total` |
| Month totals | `month.*` |
| Lifetime | `lifetime.total`, `customers_served`, `zones_covered` |

## History table columns

Map from `GET .../deliveries/` rows:

`service_date`, `time`, `customer_name`, `customer_phone`, `location`, `zone`, `meal_period`, `meal_status`, `logistics_status`, `delivered_by`, `delivery_duration_seconds`.

### Filters (allowlisted only)

| Query | Values |
|-------|--------|
| `preset` | `today`, `yesterday`, `this_week`, `this_month` |
| `date_from` / `date_to` | `YYYY-MM-DD` |
| `meal_period` | `lunch`, `dinner` |
| `zone_public_id` | UUID |
| `status` | meal: `scheduled`, `delivered`, `skipped`, `missed` |
| `logistics_status` | logistics enum |
| `page` / `page_size` | pagination |

Unknown query keys → `400`.

## Timeline

`GET .../timeline/?date=YYYY-MM-DD` (default: business today).

Empty intermediates are normal in Phase A: show `delivered` (and any other logged) events; do not treat missing accept/pick as an error.

## Route map

`GET .../route/?service_date=YYYY-MM-DD&meal_period=lunch|dinner`

- `starting_point` = Hub (`sequence: 0`)
- `stops[]` = sequence, labels, lat/lng, statuses
- Draw markers + polyline on the client; backend does not return encoded polylines

## Rankings

`GET /api/v1/web/delivery-men/rankings/?preset=today` (or date range).

Fields: `total_delivery`, `average_delivery_time_seconds`, `completion_rate`, `failed_delivery_count`.

## Empty states

| Case | Guidance |
|------|----------|
| No zone assigned | Show overview KPIs as zeros; route stops empty with “No zone assigned” |
| No deliveries in filter range | Empty table + “No deliveries in this period” |
| Timeline only has mark-delivered | Show those events; optional hint that full lifecycle needs rider app Phase B |
| Rankings empty | “No completed deliveries in this period” |

## Related admin APIs (not 360)

Approve / reject / assign-zone: `/user_management/admin/deliverymen/` — keep as HR/ops tools; 360 list is the performance entry point.
