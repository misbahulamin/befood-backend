# Admin Frontend — Service Areas

## Summary

Admin Panel section for managing BeFood service hubs (point + radius) and viewing demand / check analytics. Requires verified admin Token.

Base path: `/api/v1/web/service-areas/`

Header: `Authorization: Token <admin_token>`

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| List hubs | GET | `/api/v1/web/service-areas/?page=&page_size=&is_active=&q=` |
| Create hub | POST | `/api/v1/web/service-areas/` |
| Hub detail | GET | `/api/v1/web/service-areas/{public_id}/` |
| Edit hub | PATCH | `/api/v1/web/service-areas/{public_id}/` |
| Soft delete (deactivate) | DELETE | `/api/v1/web/service-areas/{public_id}/` |
| Activate / deactivate | POST | `/api/v1/web/service-areas/{public_id}/status/` body `{"is_active": true\|false}` |
| Request history | GET | `/api/v1/web/service-areas/requests/?from=&to=&is_serviceable=&request_kind=&q=` |
| Analytics summary | GET | `/api/v1/web/service-areas/requests/summary/?from=&to=` |

Unsupported query filters on requests → `400` + `error_code=UNSUPPORTED_FILTER`.

## Create / edit body

```json
{
  "name": "Chawkbazar Hub",
  "latitude": 22.3401,
  "longitude": 91.8301,
  "radius_km": 5,
  "description": "Primary Chattogram hub",
  "is_active": true
}
```

Response fields: `public_id`, `name`, `latitude`, `longitude`, `radius_km`, `is_active`, `description`, `created_by_email`, `created_at`, `updated_at`.

## Map picker UX (required)

1. Show Google Map on create/edit.
2. Click map → place marker → fill `latitude` / `longitude`.
3. Radius input (km) → draw circle centered on marker; update circle live when radius changes.
4. Optional “View on Map” from table row opens map at hub center with circle.

Do not force admins to type coordinates only; map click is the primary path.

## Table columns

| Service Point | Latitude | Longitude | Radius | Status | Actions |
|---------------|----------|-----------|--------|--------|---------|
| name | lat | lng | `{radius_km} KM` | Active/Inactive | View on Map, Edit, Activate/Deactivate, Delete |

## Analytics mapping

`GET .../requests/summary/` →

```json
{
  "top_requested_areas": [
    {"area_name": "GEC", "request_count": 1246}
  ],
  "top_non_serviceable_areas": [
    {
      "area_name": "Halishahar",
      "request_count": 812,
      "average_distance_km": "6.4000"
    }
  ]
}
```

| UI block | Response path |
|----------|----------------|
| Top Service Requests by Area | `top_requested_areas[]` |
| Top Non-Serviceable Locations | `top_non_serviceable_areas[]` (`average_distance_km` optional) |

Date filters: `from`, `to` (ISO date or datetime).

## Call order (create hub)

1. Open form + map.
2. Click map → lat/lng filled.
3. Set radius → preview circle.
4. POST create → refresh list.
5. Toggle status via status endpoint or PATCH `is_active`.

## API outage handling

If `GET /api/v1/web/service-areas/` returns HTML (Django debug “Page not found”) or a non-JSON body with HTTP 404, treat it as **API unavailable / not deployed** — do **not** render an empty hub table as if there were zero hubs.

Auth failures (401/403 JSON) are different: show login / permission messaging.

## Notes

- Coverage for customers uses these hubs only (not `business.DeliveryZone` fee zones).
- Soft delete deactivates; historical request rows keep FK when possible.
- Create at least one **active** production hub before asking customers to verify coverage.
