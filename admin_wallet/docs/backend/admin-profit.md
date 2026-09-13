# Admin Profit — Backend Technical Notes

## What this is

Immutable **meal profit ledger** (`MealProfitTransaction`). One row per successfully charged `OrderDelivery`, frozen at charge time from published menu slot snapshots.

## Models

`admin_wallet.models.MealProfitTransaction`

- OneToOne → `orders.OrderDelivery` (idempotency)
- FKs → customer, meal package (`MealCategory`)
- Money: `meal_price`, `food_cost`, `operational_cost`, `profit_amount`, `profit_percentage`
- `source`: `auto_delivery` | `manual_delivery` | `backfill`
- Analytics indexes on `service_date`, package, customer, meal_period

Django admin is read-only.

## Recognition hook

`orders.services.meal_payment.charge_delivered_meal` calls  
`admin_wallet.services.profit_ledger.recognize_meal_profit` after a successful charge/attach (including idempotent retries).

Shared snapshot resolution: `resolve_profit_components` (used by ledger write and legacy live calculator in `admin_wallet.services.profit`).

No profit row for Meal OFF / skip / missed / failed charge.

## APIs

- `GET /api/v1/web/admin-profit/dashboard/` — ledger aggregates only
- `GET /api/v1/web/admin-profit/history/` — paginated ledger

Auth: `IsVerifiedAdmin`. Period axis for analytics: **`service_date`**.

## Wallet dashboard

Profit fields removed from `GET /api/v1/web/admin-wallet/dashboard/` (`total_profit`, `month_profit`, `profit_by_package`).

## Backfill runbook

```bash
# Preview
python manage.py backfill_meal_profit --dry-run

# Apply (idempotent)
python manage.py backfill_meal_profit

# Optional window
python manage.py backfill_meal_profit --start-date 2026-08-01 --end-date 2026-09-13

# Compare ledger vs legacy live calculator (updated_at axis)
python manage.py backfill_meal_profit --validate
```

**Axis note:** ledger analytics use `service_date`; legacy `meal_profit_recognized()` uses `OrderDelivery.updated_at`. Expect small deltas when charge day ≠ service day.

## Tests

- `admin_wallet/tests/test_meal_profit.py`
- Wallet dashboard regressions in `admin_wallet/tests/test_admin_wallet.py`

## Verify

1. Migrate: `python manage.py migrate admin_wallet`
2. Deliver + charge a meal → one `MealProfitTransaction`
3. `GET /api/v1/web/admin-profit/dashboard/` returns non-zero totals
4. Wallet dashboard JSON has no profit keys
5. Run backfill dry-run / apply / validate on staging before production
