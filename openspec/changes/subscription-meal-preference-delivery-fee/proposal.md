## Why

Production subscribe currently creates a subscription immediately and schedules every meal period covered by the package (`meal_period_snapshot` copied from `MealCategory.meal_period`, almost always `both`). Customers need to choose Lunch, Dinner, or Both before confirming, so future delivery generation and monthly delivery-fee display follow that permanent preference—without breaking existing active/historical subscribers or old installed mobile clients.

## What Changes

- Persist customer meal preference on subscribe by writing the selected `lunch` | `dinner` | `both` into existing `CustomerSubscription.meal_period_snapshot` (no separate preference column).
- Add canonical `CustomerSubscription.quantity` (person/serving count) used for delivery-fee tiers when preference is `both`.
- Constrain preference to a subset of the package’s `meal_period` coverage (cannot broaden beyond package).
- Drive all subscription delivery generation (`ensure_subscription_deliveries` and callers) from the subscription snapshot via existing `periods_for_meal_period`.
- Add one canonical backend fee calculator and expose it via subscribe response + a lightweight `POST /api/v1/subscriptions/quote/` preview.
- Extend subscribe payload with optional `meal_preference` and `quantity`; omit → legacy fallback to package period (old clients keep working).
- Update web and mobile subscribe UX to select preference, show backend-calculated fee, then confirm.
- Admin Customer 360 surfaces preference, quantity, and calculated monthly fee (display); do not invent admin edit of preference in this change.
- **Non-goals / preserve:** meal ON/OFF, cancel cutoff logic, per-meal wallet charge-on-delivery, manual admin delivery-fee debit flow (no new auto-debit on subscribe unless product later requires it).

## Capabilities

### New Capabilities

- `subscription-meal-preference`: Subscribe-time meal preference selection, persistence on `meal_period_snapshot`, quantity field, schedule generation respect, API contract + old-client fallback.
- `subscription-delivery-fee-calculation`: Canonical monthly delivery-fee rules from preference + quantity; quote/API exposure; no client-side hardcoding of fee amounts.

### Modified Capabilities

- `package-meal-period`: Package `meal_period` remains the catalog upper bound; subscription preference may narrow but must stay within package periods.
- `customer-meal-off`: Meal OFF/ON continues to operate only on rows that exist; lunch-only/dinner-only subscriptions must not receive nonexistent period rows.
- `meal-delivery-wallet-payment`: Meal price charging unchanged; delivery fee remains a separate concern from per-meal debit.

## Impact

- **Backend:** `orders/models.py`, `orders/services/subscription_service.py`, `orders/api/subscription_*.py`, additive migration for `quantity`, new `wallet/services/subscription_delivery_fee.py`, admin customer payload, docs/tests.
- **Web:** `befood-frontend` subscriptions feature (confirm modal, API client, types, quote hook).
- **Mobile:** `befood_mobile` subscribe confirm flow (cubit/page/service/DTOs).
- **Ops/finance:** Delivery fee still collected via existing manual `charge_delivery_fee` unless a later change adds auto-charge; calculator supplies the suggested amount for UI/admin.
- **Production safety:** Existing rows keep current `meal_period_snapshot` (historically package period, typically `both`); additive `quantity` default `1`; no historical delivery rewrite.
