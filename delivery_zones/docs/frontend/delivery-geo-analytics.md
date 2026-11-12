# Delivery geo analytics (frontend)

## Ops summary vs geo analytics

| Screen | API | When to use |
|--------|-----|-------------|
| Day / meal **ops** | `GET /api/v1/web/delivery-zones/ops/summary/?service_date=&meal_period=` | Live board for **one** service date + lunch/dinner |
| Period **geo analytics** | `GET /api/v1/web/delivery-zones/analytics/matrix/?from=&to=` | Business analysis over a **date range** (density, churn, volume, rankings) |

Do not call ops/summary for month-level charts. Do not call analytics/matrix for “today’s lunch board”.

Full zone/location/sub-location CRUD: [zone-based-delivery.md](./zone-based-delivery.md).  
Backend field reference: [../backend/delivery-geo-analytics.md](../backend/delivery-geo-analytics.md).

## Auth

`Authorization: Token <admin_token>` · verified admin · prefer `X-Client-Type: web`.

## Suggested route

`/admin/delivery-zones/analytics` (or `/admin/analytics/delivery-geo`)

## Request

```http
GET /api/v1/web/delivery-zones/analytics/matrix/?from=2026-01-01&to=2026-01-31
```

Optional: `meal_period=lunch|dinner`, `zone_public_id`, `location_public_id`, `sub_location_public_id`.

Timezone for `from`/`to`: **Asia/Dhaka**. Max **366** days.

## UI building blocks

1. **Filters:** date range (required), meal period, zone → location → sub-location cascading selects.
2. **Matrix table:** expandable Zone → Location → Sub-location.
   - Customers: `total` + lifecycle (`active`, `at_risk`, `unsubscribed`, `never_subscribed`, `won_back`)
   - Churn: `churned_count`, `churn_rate_percent` (show `active_at_period_start` in tooltip)
   - Volume: `scheduled` / `delivered` / `skipped` / `missed` / `total`
   - Zone row: `assigned_delivery_man` + `workload`
3. **Unassigned callout:** `unassigned_customers` + `unassigned_volume` (and `rankings.unassigned`).
4. **Rankings panel:** highest/lowest density, highest churn (min base 5), highest delivered volume.
5. **Empty states:** zero metrics are real zeros; if `zones` is empty after a filter, show “No zones in scope”.

## Drill-down

| Action | Target |
|--------|--------|
| View customers in this sub-location | `GET /api/v1/web/customers/?sub_location_public_id=<uuid>` |
| View customers in location / zone | `location_public_id` / `zone_public_id` |
| Unassigned customers | `has_delivery_sub_location=false` |
| Churned in period (global) | `GET /api/v1/web/churn/customers/?churned_from=&churned_to=` then filter clientside by geo if needed |

Help text: customer/churn geo uses **current** assignment (not historical address at cancel time).

## Example success (truncated)

```json
{
  "from": "2026-01-01",
  "to": "2026-01-31",
  "timezone": "Asia/Dhaka",
  "zones": [],
  "rankings": {
    "churn_min_active_base": 5,
    "highest_customer_density": [],
    "highest_churn_rate": [],
    "highest_meal_volume": []
  }
}
```

## Errors

| Status | Typical cause |
|--------|----------------|
| 400 | Missing dates, range > 366 days, unknown query key |
| 401 / 403 | Auth / not admin |
| 404 | Unknown zone/location/sub-location public_id |

## QA

- [ ] Ops page still uses `ops/summary` only  
- [ ] Analytics requires `from` + `to`  
- [ ] Lunch filter changes volume only  
- [ ] Zone filter returns a single zone  
- [ ] Low-base 100% churn location absent from highest_churn_rate  
- [ ] Customer drill-down filters work  
