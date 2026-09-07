## Why

When a customer subscribes after a meal-off cutoff (for example lunch cutoff 02:00 Asia/Dhaka, subscribe at 03:00), `ensure_subscription_deliveries` still creates that day's lunch and dinner as `scheduled`. Auto-delivery cron then charges the wallet for slots that business rules say should never have been chargeable. This is a production billing defect in subscription slot generation, not in cron or wallet debit logic.

## What Changes

- Apply per-slot meal cutoff eligibility when **creating** subscription `OrderDelivery` rows (subscribe and rolling ensure).
- Reuse existing `MealOffSettings` + `meal_off_deadline` / Asia/Dhaka (settings timezone) as the single source of truth — no hardcoded cutoff times.
- For a slot whose cutoff has already passed at creation time: create the row as `skipped` with `skip_source=system` and a stable audit token in `note` (`cutoff_passed`), so support can explain the skip and auto-delivery will not charge it.
- Leave auto-delivery cron, wallet debit-on-delivered, and existing delivery rows unchanged (no backfill of already-wrong `scheduled` rows in this change).
- Add automated tests for lunch/dinner before/after cutoff and timezone-aware deadline comparison.
- Update backend subscription / meal-subscription docs to describe cutoff-aware first-day slots.

## Capabilities

### New Capabilities

- `subscription-meal-cutoff-eligibility`: When generating subscription delivery slots, each `(service_date, meal_period)` MUST be evaluated against meal-off settings deadlines in the settings timezone; slots past cutoff MUST be created already skipped with an auditable system reason, while slots still before/at cutoff remain `scheduled`.

### Modified Capabilities

- (none in `openspec/specs/` — subscription delivery continuity lives only under the archived/active subscription change folder and was never synced to main specs; this change introduces the cutoff eligibility capability as a dedicated main-spec candidate.)

## Impact

- **Primary code**: `orders/services/subscription_service.py` (`ensure_subscription_deliveries`); thin helper in `orders/services/meal_off.py` if useful.
- **Reuse**: `MealOffSettings`, `meal_off_deadline`, `meal_off_business_now` (already used by customer meal-off/on).
- **Callers unchanged in contract**: `subscribe_customer`, retrieve/current ensure paths, `ensure_subscription_deliveries` management command — behavior only changes for **newly created** slots on/after the deploy.
- **Not changed**: `auto_meal_delivery` / `auto_deliver_meals`, `charge_delivered_meal`, customer meal-off/on APIs, meal-off settings API.
- **Data**: Prefer existing fields (`status`, `skip_source`, `note`) — **no migration required** unless a later decision adds a dedicated `skip_reason` column.
- **Ops note**: Pre-existing incorrectly `scheduled` same-day slots (if any) remain until ops/manual remediation; this change is forward-safe only.
- **Docs/tests**: `orders/tests/test_customer_subscription.py` (and/or dedicated test module); backend docs under `orders/docs/backend/`.
