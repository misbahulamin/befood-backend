# Admin Profit — Backend Technical Notes

## What this is

Immutable **meal profit ledger** (`MealProfitTransaction`). Rows cover:

1. **Regular** — one row per successfully charged `OrderDelivery`, frozen at charge time from published menu slot snapshots.
2. **Guest** — one row per delivered `GuestMealOrder`, frozen at delivery realization (prepaid wallet debit already happened at purchase; realization does **not** debit again).

## Models

`admin_wallet.models.MealProfitTransaction`

- FK → `orders.OrderDelivery` (`meal_profit_transactions`; nullable for edge cases, set for normal regular/guest)
- OneToOne → `orders.GuestMealOrder` (`meal_profit_transaction`) for guest rows only
- `meal_kind`: `regular` | `guest`
- `quantity`: `1` for regular; Guest Meal order quantity for guest
- Partial unique: at most one **regular** row per `order_delivery`
- FKs → customer, meal package (`MealCategory`)
- Money: `meal_price`, `food_cost`, `operational_cost`, `profit_amount`, `profit_percentage`
- `source`: `auto_delivery` | `manual_delivery` | `backfill` | `guest_delivery` | `guest_backfill`

Django admin is read-only.

## Recognition hooks

### Regular

`orders.services.meal_payment.charge_delivered_meal` →  
`admin_wallet.services.profit_ledger.recognize_meal_profit`

Regular profit amount = published slot `profit_snapshot` (or `0.00` if missing).

### Guest

`orders.services.guest_meal.sync_guest_meals_for_delivered_delivery` (from `mark_delivery`) →  
`admin_wallet.services.profit_ledger.recognize_guest_meal_profit`

Guest formulas (Decimal, quantized to money precision):

- Revenue (`meal_price`) = `GuestMealOrder.total_amount`
- Food cost = `quantity × ingredient_cost_snapshot` (else `0.00`)
- Operational cost = `quantity × operational_cost_snapshot` (else `0.00`)
- Profit = revenue − food cost − operational cost (floored at `0.00` for storage validators)
- **`box_price` is selling price, not packaging COGS**

Service date / meal period come from the Guest Meal order (not purchase `created_at`).

Idempotent via unique `guest_meal_order`. Retries of mark-delivered must not double-count.

## APIs

- `GET /api/v1/web/admin-profit/dashboard/` — ledger aggregates (includes guest when realized)
- `GET /api/v1/web/admin-profit/history/` — paginated ledger

Additive dashboard fields (range scope):

- `regular_revenue` / `guest_revenue` (sum → `range_revenue`)
- `regular_food_cost` / `guest_food_cost` (sum → `range_food_cost`)
- `regular_profit` / `guest_profit` (sum → `range_profit`)
- `regular_meals_served` / `guest_meals_served` / `total_meals_served` (sum of `quantity`)
- Legacy `range_deliveries` = ledger **row** count (not delivery stops)

History rows expose `meal_kind`, `quantity`, `guest_meal_public_id` (nullable).

Auth: `IsVerifiedAdmin`. Period axis: **`service_date`**.

## Wallet dashboard

Profit fields remain removed from `GET /api/v1/web/admin-wallet/dashboard/`.

## Backfill / guest reconcile

```bash
# Regular charged deliveries missing rows
python manage.py backfill_meal_profit --dry-run
python manage.py backfill_meal_profit

# Delivered guest orders missing realization (dry-run default)
python manage.py reconcile_guest_meal_profit
python manage.py reconcile_guest_meal_profit --apply
python manage.py reconcile_guest_meal_profit --start-date 2026-11-01 --end-date 2026-11-30 --apply
```

Do not run `--apply` on production without explicit approval.

## Tests

- `admin_wallet/tests/test_meal_profit.py`
- Guest delivery path: `orders/tests/test_guest_meal.py` (mark-delivered recognizes guest profit once)
- Wallet dashboard regressions in `admin_wallet/tests/test_admin_wallet.py`

## Verify

1. Migrate: `python manage.py migrate admin_wallet`
2. Deliver + charge a regular meal → one regular `MealProfitTransaction`
3. Deliver a stop with guest boxes → guest status `delivered` + one guest ledger row per GuestMealOrder; wallet not re-debited for guest
4. `GET /api/v1/web/admin-profit/dashboard/` includes guest contributions in totals and breakdowns
5. Ops dashboard `total_meals_served` = regular delivered stops + delivered guest quantities; `today_delivery` remains stop count
