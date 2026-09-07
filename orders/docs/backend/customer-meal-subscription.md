# Customer meal subscription (backend)

## Quick summary

Verified customers **subscribe once** to an open-ended meal plan (`MealCategory` with `is_subscribable=true`). Service continues until cancel. The backend does **not** create a month-bounded `Order` on subscribe.

Wallet: `OrderWalletSettings.min_wallet_balance_to_order` is a **subscribe eligibility check only**. Debit still happens when a slot is marked `delivered`.

Rolling slots: `ensure_subscription_deliveries` fills `OrderDelivery` rows from **today through the last day of next month**, only for months with a published `MonthlyMenuSchedule`. Unpublished months are skipped; the subscription stays `active`.

### First-day meal cutoff eligibility

When creating **new** slots, the generator consults `MealOffSettings` (same source as `/orders/meal-off-settings/`):

- Timezone: settings IANA zone (production default `Asia/Dhaka`)
- Lunch / dinner deadlines: `lunch_off_time` / `dinner_off_time` on the **service date**
- If business now is **strictly after** that deadline for today’s `(service_date, meal_period)`, the new row is created as `skipped` with `skip_source=system` and `note=cutoff_passed` (audit). Auto-delivery only charges `scheduled` slots, so these are not wallet-debited.
- Future dates in the horizon remain `scheduled`.
- Existing delivery rows are **never** rewritten by ensure (forward-only; no migration / no backfill of pre-fix over-scheduled rows).

Example: lunch cutoff `02:00`, subscribe at `03:00` on a `both` plan → today’s lunch `skipped` / `cutoff_passed`, today’s dinner still `scheduled` if dinner cutoff has not passed.

| Client | Method | Path | Why |
|--------|--------|------|-----|
| Customer | `GET` | `/api/v1/subscription-plans/` | Active subscribable catalog |
| Customer | `POST` | `/api/v1/subscriptions/` | Subscribe (`plan_public_id`) |
| Customer | `GET` | `/api/v1/subscriptions/current/` | Active subscription or null |
| Customer | `GET` | `/api/v1/subscriptions/{public_id}/` | Own detail + slots |
| Customer | `POST` | `/api/v1/subscriptions/current/cancel/` | Cancel; skip future slots |
| Customer | `POST` | `/orders/` | **Retired** — always `409 SUBSCRIBE_REQUIRED` |
| Customer | `GET` | `/orders/orderable-months/` | **Retired** — same `409` |
| Customer | `GET` | `/orders/current-package/` | Active subscription payload (compat) |
| Ops | command | `ensure_subscription_deliveries` | Daily rolling-horizon backfill |
| Ops | publish | `publish_schedule` | Also runs ensure after menu publish |

## Subscribe

Service: `subscribe_customer` in `orders/services/subscription_service.py`.

1. Plan must be `is_active` and `is_subscribable`.
2. At most one `active` `CustomerSubscription` per customer (DB unique + service check). Already-subscribed is checked **before** the wallet gate.
3. Wallet missing → balance `0`. Frozen wallet → reject. Balance `<` minimum → reject. **No ledger write.**
4. Snapshots: `meal_name_snapshot`, `meal_period_snapshot`. `started_on` = meal-off timezone today.
5. Same transaction: `ensure_subscription_deliveries` (applies meal-off cutoff eligibility for **today’s** new slots — see above).

## Cancel

`cancel_effective_on` = today. `scheduled` slots with `service_date > today` become `skipped` / `skip_source=system`. Today’s slots are unchanged (meal-off still applies). Meal-off must **not** complete or cancel the subscription.

## Rolling horizon

- Window: `business_today()` … last day of next calendar month.
- Idempotent unique `(subscription, service_date, meal_period)`.
- Do not generate after `status=cancelled`.
- End of a month does **not** complete the subscription.
- Cutoff eligibility applies only at **create** time for the current business day; re-running ensure does not flip an existing `scheduled` row to `skipped`.

## Manual QA (cutoff-aware subscribe)

1. Set meal-off settings: lunch `02:00:00`, dinner `16:00:00`, timezone `Asia/Dhaka`.
2. Ensure the current month menu is published for the plan package.
3. Subscribe at ~01:59 → today’s lunch and dinner should be `scheduled`.
4. Cancel / use a fresh customer; subscribe at ~02:01 → today’s lunch `skipped` / `system` / `cutoff_passed`, dinner `scheduled`.
5. Fresh customer; subscribe at ~16:01 → both today’s lunch and dinner `skipped` with `cutoff_passed`.
6. Confirm lunch/dinner auto-delivery cron does **not** deliver or charge cutoff-skipped slots.
7. Confirm a customer who subscribed before the fix and already has a wrongly `scheduled` same-day lunch is **not** auto-corrected (forward-only).

## Historical orders

`create_meal_order()` remains an internal helper for tests and history. Customer HTTP create is retired. In-flight rows are migrated by `migrate_in_flight_orders` (`orders/migrations/0013_...`).
