# Local reconciliation after guest profit apply

**DB:** local `db.sqlite3`  
**After:** `reconcile_guest_meal_profit --apply`

## Quantities

| Metric | Regular | Guest | Total |
|---|---:|---:|---:|
| Meals served (lifetime) | 66 | 2 | 68 |
| Today delivery stops | 1 | — | 1 |

Dashboard API: `total_meals_served=68`, `regular_meals_served=66`, `guest_meals_served=2`, `today_delivery=1`.

## November 2026 profit range (1–30)

| Metric | Regular | Guest | Total |
|---|---:|---:|---:|
| Revenue | 33.55 | 140.00 | 173.55 |
| Food cost | 30.50 | 61.00 | 91.50 |
| Profit | 3.05 | 79.00 | 82.05 |
| Meals served | 1 | 2 | 3 |

Guest ledger row: qty=2, meal_price=140.00, food_cost=61.00, profit=79.00, service_date=2026-11-16.

## Guest Meals admin summary

| Field | Value |
|---|---:|
| prepaid_order_value (legacy `revenue`) | 575.50 |
| delivered_recognized_revenue | 140.00 |
| realized_guest_profit | 79.00 |

Equations hold: Total = Regular + Guest for revenue/cost/profit/meals.
