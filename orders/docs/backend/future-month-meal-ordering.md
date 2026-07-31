# Backend: future-month meal ordering

## Quick summary

Verified customers can place a meal package for a **selected meal month** (current local month through +12 months). The selected month is stored on `Order.order_month` (`YYYY-MM`). Create requires a **published** `MonthlyMenuSchedule` for that meal + month, then existing month-lock and wallet-minimum gates.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/orders/orderable-months/?meal_public_id=` | Month picker data (13 months + flags) |
| `GET` | `/meals/order-menu-preview/?meal_public_id=&year=&month=` | Pre-order published menu preview |
| `POST` | `/orders/` | Create order; optional `year` + `month` |

## Permissions

| Endpoint | Who |
|----------|-----|
| orderable-months, order create, order-menu-preview | `IsVerifiedCustomer` |
| my-package-menu (unchanged) | Ownership-scoped; empty without an order |

## Key models / fields

- `Order.order_month` — selected meal month (`YYYY-MM`); unique non-cancelled per customer
- `MonthlyMenuSchedule.status=published` — publish gate via `published_schedule_for_meal`
- `OrderWalletSettings.min_wallet_balance_to_order` — unchanged eligibility

## Business validation (create order)

1. Meal active + `total_price` set  
2. `year`/`month` both omitted → current month; both required if either sent; must be in current … +12  
3. Published menu for meal + target month  
4. No non-cancelled order for that `order_month`  
5. Wallet balance ≥ minimum (no debit); frozen wallet rejected  

## Period rules

| Selection | Reference date for duration |
|-----------|-----------------------------|
| Current month | `timezone.localdate()` |
| Future month | Day 1 of that month |

`order_month` is always the selected `YYYY-MM` (including six_months / yearly start stamp).

## Services

| Module | Role |
|--------|------|
| `orders.services.meal_month` | Window validators, labels, horizon |
| `orders.services.order_duration.calculate_order_period` | `target_year` / `target_month` |
| `orders.services.order_service.create_meal_order` | Full eligibility + create |
| `orders.services.orderable_months` | Picker payload |
| `meals.services.package_menu.build_order_menu_preview_for_meal` | Pre-order preview |

## Errors (create)

| Condition | Field / shape |
|-----------|----------------|
| Partial year/month | `year` + `month` |
| Out of window | `month` |
| Menu not published | `non_field_errors` |
| Month lock / wallet | `non_field_errors` |

## How to verify

```bash
python manage.py test orders.tests.test_future_month_ordering
```

OpenSpec: `openspec/changes/future-month-meal-ordering/`
