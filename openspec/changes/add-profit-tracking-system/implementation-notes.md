# Implementation notes — add-profit-tracking-system

## Confirmed recognition inputs (task 1.1)

- Live calculator: `admin_wallet/services/profit.py`
  - Charged deliveries: `payment_status=charged`, `charged_amount` set
  - Package via `orders.services.subscription_parent.delivery_meal`
  - Slot via `meals.services.slot_pricing.resolve_published_slot_for_delivery`
  - Profit = `MonthlyMenuSlot.profit_snapshot` (missing → `0.00`)
  - Revenue = `OrderDelivery.charged_amount`
- Charge metadata in `orders/services/meal_payment.py` already stores slot price / cost / profit strings in wallet txn metadata; ledger freezes the same snapshot values at write time.

## Confirmed hook points (task 1.2)

- Auto: `scripts/cron/run_auto_deliver.sh` → `auto_deliver_meals` → `run_auto_delivery` → `mark_delivery_and_notify` → `mark_delivery` → `charge_delivered_meal`
- Manual admin: mark-delivery API → same `mark_delivery` → `charge_delivered_meal`
- Profit recognition is hooked inside `charge_delivered_meal` after a successful charge/attach so both paths share one write.

## BREAKING wallet dashboard fields to remove (task 1.3)

Removed from `GET /api/v1/web/admin-wallet/dashboard/`:

| Field | Replacement |
|-------|-------------|
| `total_profit` | `GET /api/v1/web/admin-profit/dashboard/` → `lifetime_profit` |
| `month_profit` | `…/admin-profit/dashboard/` → `month_profit` |
| `profit_by_package` | `…/admin-profit/dashboard/` → `profit_by_package` |

Admin Panel must stop reading profit from the wallet dashboard in the same release.
