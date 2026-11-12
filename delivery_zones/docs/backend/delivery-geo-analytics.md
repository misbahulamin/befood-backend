# Delivery geo analytics (backend)

## What is this?

Verified-admin **period** analytics for delivery geography: Zone → Location → Sub-location. Use it for growth analysis (density, churn, meal volume, rider load). For **one day / one meal** live ops, keep using `ops/summary`.

## Endpoint

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/web/delivery-zones/analytics/matrix/` | Hierarchical matrix + rankings |

Auth: `Authorization: Token <admin_token>` + verified admin (`IsVerifiedAdmin`).  
`401` unauthenticated · `403` non-admin · `400` bad query · `404` unknown hierarchy UUID.

## Query parameters

| Param | Required | Notes |
|-------|----------|-------|
| `from` | yes | `YYYY-MM-DD` (Asia/Dhaka calendar) |
| `to` | yes | Inclusive end; must be ≥ `from`; max span **366** days |
| `meal_period` | no | `lunch` or `dinner`; omit = both |
| `zone_public_id` | no | Restrict to one zone (unknown → `404`) |
| `location_public_id` | no | Restrict to one location (+ its zone) |
| `sub_location_public_id` | no | Restrict to one sub-location |

Unknown query keys → `400` `UNSUPPORTED_FILTER`.

## Attribution rules

| Metric | Rule |
|--------|------|
| Customer density / lifecycle | Current `CustomerProfile.delivery_sub_location` → location → zone |
| Period churn | Cancels in `[from, to]` attributed to customer’s **current** geo |
| Meal volume | Prefer `OrderDelivery.logistics_sub_location`, else customer sub-location |
| Rider workload | Zone primary `assigned_delivery_man` + zone volume for the period |

Churn rate = `churned_count ÷ active_at_period_start` (node-scoped). If base is `0`, rate is `0` (churned_count may still be > 0).

## Response shape (summary)

```json
{
  "from": "2026-01-01",
  "to": "2026-01-31",
  "meal_period": null,
  "timezone": "Asia/Dhaka",
  "attribution": {
    "customers_and_churn": "current_assignment",
    "volume": "logistics_sub_location_then_customer_sub_location"
  },
  "unassigned_customers": { "total": 0, "active": 0, "at_risk": 0, "unsubscribed": 0, "never_subscribed": 0, "won_back": 0 },
  "unassigned_volume": { "scheduled": 0, "delivered": 0, "skipped": 0, "missed": 0, "total": 0 },
  "zones": [
    {
      "public_id": "...",
      "name": "Zone 1",
      "code": "zone-1",
      "assigned_delivery_man": { "public_id": "...", "email": "...", "first_name": "Rahim", "last_name": "" },
      "customers": { "total": 10, "active": 7, "at_risk": 1, "unsubscribed": 2, "never_subscribed": 0, "won_back": 0 },
      "churn": { "churned_count": 2, "active_at_period_start": 20, "churn_rate_percent": 10.0 },
      "volume": { "scheduled": 0, "delivered": 40, "skipped": 5, "missed": 0, "total": 45 },
      "workload": { "delivered": 40, "total": 45, "unassigned_zone": false },
      "locations": [
        {
          "public_id": "...",
          "name": "Chawkbazar",
          "customers": {},
          "churn": {},
          "volume": {},
          "sub_locations": [
            {
              "public_id": "...",
              "name": "Gate A",
              "is_default": false,
              "customers": {},
              "churn": {},
              "volume": {}
            }
          ]
        }
      ]
    }
  ],
  "rankings": {
    "churn_min_active_base": 5,
    "highest_customer_density": [],
    "lowest_customer_density": [],
    "highest_churn_rate": [],
    "highest_meal_volume": [],
    "unassigned": { "customers": {}, "churn": {}, "volume": {} }
  }
}
```

Active zones/locations/sub-locations in scope appear even with zero metrics (full hierarchy mode).

### Rankings

- Density uses location `customers.total`.
- Meal volume ranking uses **delivered** count.
- Highest churn excludes locations with `active_at_period_start < 5`.

## Error codes

| Code | HTTP | When |
|------|------|------|
| `DATE_RANGE_REQUIRED` | 400 | Missing `from` or `to` |
| `INVALID_DATE` | 400 | Bad date format |
| `INVALID_DATE_RANGE` | 400 | `to` < `from` |
| `DATE_RANGE_TOO_LONG` | 400 | > 366 days |
| `INVALID_MEAL_PERIOD` | 400 | Not lunch/dinner |
| `UNSUPPORTED_FILTER` | 400 | Unknown query key |
| `INVALID_PUBLIC_ID` | 400 | Malformed UUID |
| `ZONE_NOT_FOUND` / `LOCATION_NOT_FOUND` / `SUB_LOCATION_NOT_FOUND` | 404 | Unknown filter UUID |

## How to verify

```bash
python manage.py test delivery_zones.tests.test_geo_analytics -v2
```

Related: day ops → `docs/backend/zone-based-delivery.md` · frontend → `docs/frontend/delivery-geo-analytics.md`.
