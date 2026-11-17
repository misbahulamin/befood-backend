# Admin Guest Meals — Frontend Integration

## Summary

`GET /api/v1/web/orders/guest-meals/` returns a paginated list plus a `summary` object for `/admin/guest-meals`.

## Summary field meanings

| Field | Meaning |
|-------|---------|
| `order_count` | Number of Guest Meal orders in the filter |
| `box_quantity` | Sum of ordered `quantity` (all statuses in filter) |
| `revenue` | **Legacy** prepaid order value (same as `prepaid_order_value`) |
| `prepaid_order_value` | Sum of `total_amount` for filtered orders (scheduled + delivered + cancelled) |
| `delivered_recognized_revenue` | Sum of `total_amount` for **delivered** orders only |
| `realized_guest_profit` | Sum of guest `MealProfitTransaction.profit_amount` for orders in the filter |
| `scheduled_box_quantity` | Boxes still scheduled |
| `delivered_box_quantity` | Boxes delivered |
| `cancelled_box_quantity` | Boxes cancelled |

Do **not** label prepaid order value as realized delivered revenue. Scheduled guest payments inflate `prepaid_order_value` / legacy `revenue` but not `delivered_recognized_revenue`.

## Auth

Verified admin. Web client.
