# Admin Ops Dashboard — Frontend Integration

## Summary

`GET /api/v1/web/admin-dashboard/summary/` returns home KPIs for `/admin/dashboard`.

## Meals served vs delivery stops

| Field | Meaning |
|-------|---------|
| `total_meals_served` | Lifetime **food boxes**: delivered regular stops + delivered Guest Meal quantities |
| `regular_meals_served` | Lifetime delivered regular meal boxes (one per delivered stop) |
| `guest_meals_served` | Lifetime sum of delivered Guest Meal `quantity` |
| `monthly_meals_served` | Month-to-date food boxes (Asia/Dhaka `service_date`) |
| `monthly_regular_meals_served` / `monthly_guest_meals_served` | Month-to-date breakdown |
| `today_meals_served` | Today food boxes |
| `today_regular_meals_served` / `today_guest_meals_served` | Today breakdown |
| `today_delivery` | Today **delivery stops** (unchanged; guest boxes do not inflate this) |
| `total_delivery_stops` / `monthly_delivery_stops` | Additive stop totals |

Do **not** treat `today_delivery` as food-box count. Catalog card counts menu items separately.

## Auth

Verified admin. Web client.
