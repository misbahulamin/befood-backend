## Why

Admins can create meal packages by duration (`daily` / `weekly` / `monthly` / …) but cannot say whether a package covers lunch, dinner, or both. Plan editor finalize, per-meal pricing, and order delivery slots all assume two servings per service day (`days × 2`). That over-counts single-period packages (e.g. monthly dinner-only should be 28–31 meals, not 56–62) and under-documents daily both (2 meals) vs daily lunch-only (1 meal).

## What Changes

- Add a required **meal period** on meal package create/update: `lunch` | `dinner` | `both`.
- Derive **periods per day** from that choice: `lunch` or `dinner` → 1; `both` → 2.
- Derive **expected serving count** as `service_days(meal_type, cycle year/month) × periods_per_day`:
  - daily + lunch/dinner → 1; daily + both → 2
  - monthly + dinner → calendar days in month (28/29/30/31)
  - monthly + both → `days × 2` (60/62 for 30/31-day months)
  - weekly / half_monthly / longer types follow the same day-count rules already used for order duration, multiplied by periods per day
- Plan editor summary, main-servings finalize validation, and `per_meal_rate` MUST use the **package’s** expected servings for that cycle month (not a global cycle `days × 2` for every package).
- Order delivery slot generation MUST create only the periods the package includes (and use the package’s chosen single period when not `both`).
- Public/offering `per_meal_price` MUST divide by the same expected serving count for the package in the present month.
- **BREAKING** (admin meal create/update): `meal_period` becomes required; clients that omit it fail validation.
- **BREAKING** (fulfillment counts): packages with `lunch` or `dinner` no longer generate or expect two slots per service day.

## Capabilities

### New Capabilities

- `package-meal-period`: Meal package lunch/dinner/both selection, periods-per-day and expected-servings math, and API/admin exposure of `meal_period`.
- `period-aware-order-slots`: Order delivery slot generation and completion rules aligned to the package’s meal period (and duration).

### Modified Capabilities

- `meal-cycle-planning`: Expected main servings and plan summary targets become package-period-aware instead of always `cycle_days × 2`.
- `meal-cycle-costing`: `per_meal_rate` divisor uses the plan package’s expected servings for the cycle month.

## Impact

- Models/API: `MealCategory` (+ serializers, admin, OpenAPI), meal create/update/list/detail payloads.
- Services: `meals/services/pricing.py`, `cycle_calculations.py`, `meal_offering.py`; cycle plan finalize/summary; possibly `MealCycle.total_meals` semantics (calendar reference vs per-plan target).
- Orders: `orders/services/order_delivery.py` (and related tests) so slot counts match lunch/dinner/both.
- Menu schedule may remain full lunch+dinner calendar for kitchen planning; package period governs package costing and order fulfillment counts (clarify in design).
- Tests and backend/frontend docs under `meals/docs/` and `orders/docs/` as needed.
- Existing packages need a migration default (recommended: `both` to preserve current `× 2` behavior).
