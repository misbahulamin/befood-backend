# Frontend — Admin published menu dual pricing

## Summary

Admin published-menus page (`/admin/published-menus/{menu_id}`) maps to:

`GET /meals/menu-schedules/{public_id}/`

Backend now returns **subscriber** and **Instant** pricing per slot. **Do not calculate prices in the frontend** — render response fields only.

## Auth

`Authorization: Token <admin_token>`  
`X-Client-Type: web` (optional; admin web)

## Table columns (recommended)

| Column | API field |
| --- | --- |
| Meal / ingredients | `ingredients` (or display name derived from them) |
| Ingredient cost | `selected_ingredients_cost` |
| Subscriber price | `subscriber_price` or `subscriber_pricing.final_price` (same as `final_meal_price`) |
| Subscriber profit | `subscriber_pricing.profit_amount` (+ optional `%` from `subscriber_pricing.profit_percent`) |
| Instant price | `instant_price` or `instant_pricing.final_price` |
| Instant profit | `instant_pricing.profit_amount` (+ optional `%` from `instant_pricing.profit_percent`) |

## Field map

| Field | Meaning |
| --- | --- |
| `final_meal_price` | Legacy subscriber selling price (keep using for old clients) |
| `selected_ingredients_cost` | Raw ingredient cost used for both ladders |
| `operational_cost` | Per-meal operational cost |
| `subscriber_pricing` | Nested `{ profit_percent, profit_amount, final_price }` |
| `instant_pricing` | Nested Instant ladder from live Instant settings |
| `subscriber_price` / `instant_price` | Flat aliases for table cells |

Null when draft or unpriceable — show empty / “—”; never invent zeros.

## Instant settings change

1. Admin patches `PATCH /meals/instant-meal-settings/` (`profit_percent`).
2. Refresh schedule detail (`GET` again).
3. Instant columns update; subscriber `final_meal_price` stays the same.
4. **No menu republish** required for Instant ladder refresh.

## Don’t

- Don’t recompute `ingredient × percent` in JS (rounding will diverge).
- Don’t charge wallets from Instant price — delivery debit uses subscriber slot snapshot.
- Don’t remove `final_meal_price` from parsers until all clients migrate.

## Related

- Backend: `meals/docs/backend/monthly-meal-menu-schedule.md` (§6.1b)
- Instant settings: `meals/docs/frontend/instant-meal-offering.md`
- Slot charge isolation: `meals/docs/frontend/slot-final-price-and-menu-isolation.md`
