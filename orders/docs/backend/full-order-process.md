# Full Order Process (Backend)

## Quick summary

**New service** is `CustomerSubscription` + rolling `OrderDelivery` slots. See [`customer-meal-subscription.md`](customer-meal-subscription.md).

Historical `Order` rows remain for past monthly packages. Customer `POST /orders/` is retired (`409 SUBSCRIBE_REQUIRED`). Admins still list historical orders and mark deliveries.

| Client | Method | Path | Why |
|--------|--------|------|-----|
| Customer | `POST` | `/api/v1/subscriptions/` | Subscribe to a plan |
| Customer | `POST` | `/orders/` | Retired (`409 SUBSCRIBE_REQUIRED`) |
| Customer / Admin | `GET` | `/orders/` | List historical orders (own for customer; **all** for verified admin) |
| Customer | `GET` | `/orders/my-orders/` | Alias list of own orders + progress |
| Customer / Admin | `GET` | `/orders/{id}/` | Order detail + deliveries (scoped by role) |
| Customer | `GET` | `/orders/current-package/` | Active **subscription** (or null) |
| Customer | `POST` | `/orders/{id}/cancel/` | Cancel historical order before start |
| Admin | `GET` | `/orders/today-board/` | Kitchen board (also `/api/v1/web/orders/today-board/`) |
| Admin | `POST` | `/api/v1/web/subscriptions/{id}/deliveries/{delivery_id}/mark` | Mark subscription slot |
| Admin | `POST` | `/orders/{id}/deliveries/{delivery_id}/mark` | Mark historical order slot |

Auth: `Authorization: Token <key>`.

Admin mark (and the nested wallet charge on `delivered`) locks only the delivery row on PostgreSQL (`SELECT FOR UPDATE OF` the delivery table) so nullable `order` / `subscription` outer joins do not raise `FOR UPDATE cannot be applied to the nullable side of an outer join`.

## Permissions matrix

| Action | Customer (verified) | Admin (`IsVerifiedAdmin`) |
|--------|---------------------|---------------------------|
| Create order | Yes | No (use customer account) |
| `GET /orders/` list | Own orders only | All orders |
| View own order / progress | Yes | Yes (all orders) |
| Mark delivery | No | Yes (`/api/v1/web/orders/...`) |
| Admin today-board | No (`403`) | Yes |

## Key models

### `Order`
Commercial package: snapshots, `order_status`, date window, `order_month`.

Statuses: `pending` → `confirmed` → `active` → `completed` / `cancelled`.

### `OrderDelivery`
One fulfillment slot:

| Field | Meaning |
|-------|---------|
| `service_date` | Calendar day of delivery |
| `meal_period` | `lunch` or `dinner` (daily uses `lunch`) |
| `status` | `scheduled` / `delivered` / `skipped` / `missed` |
| `marked_by` / `marked_at` | Who marked and when |
| `note` | Optional ops note |

Unique: `(order, service_date, meal_period)`.

## Business rules

1. **Daily:** exactly **1** slot; after `delivered`, order → `completed`.
2. **Monthly:** **2 slots/day** for every day in the calendar month → **60** (30-day) or **62** (31-day).
3. **Weekly / half_monthly:** 2 slots/day across `[order_start_date, order_end_date]`.
4. Month lock: one non-cancelled package per customer per `order_month` (unchanged).
5. Customers never mark deliveries; progress is read-only.
6. Duplicate mark with the same status is idempotent; changing an already-terminal slot fails.

## Workflows

### A. Customer places order

1. `POST /orders/` body:
```json
{ "meal_public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "customer_note": "After 1 PM" }
```
(Use meal `public_id` from `/meals/` — see `meals/docs/frontend/meal-public-uuid.md`.)
2. Response `201` includes snapshots, `meal_public_id`, status `confirmed`, `deliveries[]`, and progress:
   - `expected_deliveries`, `delivered_count`, `remaining_count`, `active_days_this_month`
3. Admin can immediately see the order on `GET /api/v1/web/orders/`.

### B. Admin fulfills deliveries

1. `GET /api/v1/web/orders/today-board/?service_date=2026-07-10`
2. Pick a delivery id, then:
```http
POST /api/v1/web/orders/{order_id}/deliveries/{delivery_id}/mark
{ "status": "delivered", "note": "" }
```
3. Daily packages complete automatically after the first delivery.
4. Multi-day packages complete when all slots are terminal, or via lifecycle sync after end date (remaining → `missed`).

### C. Lifecycle sync (cron)

```bash
python manage.py sync_order_lifecycle
python manage.py sync_order_lifecycle --backfill-deliveries
python manage.py sync_order_lifecycle --date 2026-07-10
```

**When to run:** daily (e.g. after midnight business TZ) to activate due `confirmed` orders and close expired packages. Use `--backfill-deliveries` once after deploy for legacy orders.

## Admin filters (`GET /api/v1/web/orders/`)

| Query | Values / format | Effect |
|-------|-----------------|--------|
| `meal_type` | `daily`, `weekly`, `half_monthly`, `monthly`, … | Filter `meal_type_snapshot` |
| `order_status` | `confirmed`, `active`, `completed`, … | Exact status |
| `activity` | `active` / `inactive` | In-window non-terminal vs completed/cancelled/out-of-window |
| `order_month` | `YYYY-MM` | Month key |
| `created_after` / `created_before` | ISO datetime | Created range |
| `start_date` / `end_date` | `YYYY-MM-DD` | Order window bounds |

## Today board query params

| Param | Meaning |
|-------|---------|
| `service_date` | Default today |
| `week_of_month` | ISO week number within the month of `service_date` |
| `meal_period` | `lunch` / `dinner` |
| `status` | Delivery status filter |

## Status glossary

| Order status | Meaning |
|--------------|---------|
| `confirmed` | Paid/placed; waiting for start date |
| `active` | Inside service window / being fulfilled |
| `completed` | Finished (daily one-shot or all slots done) |
| `cancelled` | Cancelled before start |

| Delivery status | Meaning |
|-----------------|---------|
| `scheduled` | Still to deliver |
| `delivered` | Fulfilled |
| `skipped` | Intentionally skipped |
| `missed` | Past end date without delivery |

## Error cheat sheet

| HTTP | When |
|------|------|
| 400 | Validation / cannot mark / bad date |
| 401 | Missing auth |
| 403 | Customer hits admin routes / unverified |
| 404 | Order/delivery missing or not owned |
| 409 | Delivery already terminal with different status |

## How to verify

```bash
python manage.py test orders.tests.test_full_order_process orders.tests.test_orders
```

OpenSpec: `openspec/changes/full-order-process/`.
