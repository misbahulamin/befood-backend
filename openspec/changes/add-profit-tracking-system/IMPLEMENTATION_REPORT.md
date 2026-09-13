# Implementation report — add-profit-tracking-system

## 1. Files changed / added

**Added**
- `admin_wallet/services/profit_ledger.py` — recognition + shared snapshot resolution
- `admin_wallet/services/profit_analytics.py` — ledger-only dashboard/history queries
- `admin_wallet/api/profit_serializers.py`, `profit_views.py`, `profit_urls.py`
- `admin_wallet/management/commands/backfill_meal_profit.py`
- `admin_wallet/migrations/0006_meal_profit_transaction.py`
- `admin_wallet/tests/test_meal_profit.py`
- `admin_wallet/docs/frontend/admin-profit.md`
- `admin_wallet/docs/backend/admin-profit.md`
- `openspec/changes/add-profit-tracking-system/implementation-notes.md`

**Updated**
- `admin_wallet/models.py` — `MealProfitTransaction`
- `admin_wallet/admin.py` — read-only admin
- `admin_wallet/services/profit.py` — uses shared `resolve_profit_components`
- `admin_wallet/services/queries.py` — profit fields removed from wallet dashboard
- `admin_wallet/api/serializers.py`, `views.py` — wallet dashboard contract
- `orders/services/meal_payment.py` — recognition hook after successful charge
- `core/urls.py` — mount `/api/v1/web/admin-profit/`
- `admin_wallet/docs/frontend/admin-wallet.md`
- `admin_wallet/tests/test_admin_wallet.py`

## 2. New model / migration

- Model: `MealProfitTransaction` (`admin_wallet`)
- Migration: `admin_wallet/migrations/0006_meal_profit_transaction.py`
- Run: `python manage.py migrate admin_wallet`

## 3. Delivery hook

- Path: `mark_delivery` → `charge_delivered_meal` → `recognize_meal_profit`
- File: `orders/services/meal_payment.py`
- Covers auto cron and manual admin mark-delivered (shared charge path)

## 4. Profit calculation location

- Write: `admin_wallet/services/profit_ledger.py` (`resolve_profit_components`, `recognize_meal_profit`)
- Read/analytics: `admin_wallet/services/profit_analytics.py`
- Legacy live scan (validation only): `admin_wallet/services/profit.py`

## 5. Historical backfill

```bash
python manage.py backfill_meal_profit --dry-run
python manage.py backfill_meal_profit
python manage.py backfill_meal_profit --validate
# optional: --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

## 6. New APIs

| Method | Path |
|--------|------|
| GET | `/api/v1/web/admin-profit/dashboard/` |
| GET | `/api/v1/web/admin-profit/history/` |

## 7. Removed wallet dashboard fields (BREAKING)

- `total_profit`
- `month_profit`
- `profit_by_package`

## 8. Test results

```text
python manage.py test admin_wallet.tests.test_meal_profit admin_wallet.tests.test_admin_wallet
→ OK (24 tests)
```
