# Test Meal Orders (Backend)

Lifetime Test Meal trials for **authenticated non-subscribers**. Orders confirm without wallet debit or online payment (`confirmed` + `unpaid` + `manual`), enforce a lifetime quota of two accepted orders, reuse published slot pricing and meal-off cutoff (Asia/Dhaka), and create a standalone `OrderDelivery` stop for ops/kitchen/board.

## Quick summary

| Concern | Behavior |
|---------|----------|
| Who | Verified customer with **no** active subscription |
| What | One meal for `service_date` + `meal_period` (`lunch` \| `dinner`) + package |
| Price | Published slot `final_meal_price_snapshot` + `OrderWalletSettings.test_meal_box_price` |
| Pay | Manual admin recording only in v1 (no wallet debit, no gateway) |
| Quota | Count of accepted `TestMealOrder` rows per customer (includes later cancel/deliver) |
| Limit default | `test_meal_lifetime_quota = 2`, box default `10.00` |
| Fulfillment | Dedicated `OrderDelivery` with `test_meal_order` set; `order`/`subscription` null |
| Delivery charge | Mark-delivered syncs Test Meal status **without** `charge_delivered_meal` |

## Settings

Admin: `GET/PATCH /api/v1/web/orders/order-wallet-settings/`

| Field | Default | Notes |
|-------|---------|-------|
| `test_meal_box_price` | `10.00` | Snapshotted on each Test Meal order |
| `test_meal_lifetime_quota` | `2` | Accepted-order lifetime cap |

## Models

- `TestMealOrder` (`PublicIdMixin`): package, customer, service slot, price snapshots, address snapshots, delivery windows, `order_status`, `payment_status`, payment fields, idempotency key.
- `TestMealPaymentEvent`: audit for record/correct/refund.
- `TestMealFunnelEvent`: deduped CTA instrumentation (`event_name` + `client_event_id` + customer or correlation).
- `OrderDelivery.test_meal_order`: nullable FK; parent exclusivity for new rows is exactly one of (`order`, `subscription`, `test_meal_order`).

### Order status transitions

`confirmed` → `preparing` → `out_for_delivery` → `delivered`  
Also: `confirmed`/`preparing`/`out_for_delivery` → `cancelled` or `failed` (terminal).

Payment statuses (`unpaid` \| `paid` \| `refunded`) are independent of fulfillment.

## Customer APIs

Base: `/api/v1/test-meals/`  
Auth: verified customer. Scope is always the authenticated customer.

| Method | Path | Side effects |
|--------|------|----------------|
| `GET` | `/eligibility/` | None |
| `GET` | `/packages/` | None |
| `POST` | `/quote/` | None |
| `POST` | `/orders/` | Create order + delivery stop |
| `GET` | `/orders/` | Paginated history |
| `GET` | `/orders/{public_id}/` | Detail |
| `POST` | `/funnel-events/` | Optional instrumentation |

### Create body

```json
{
  "service_date": "2026-11-17",
  "meal_period": "lunch",
  "package_public_id": "<uuid>",
  "address_public_id": "<uuid>",
  "special_instructions": "Less spicy"
}
```

Optional header: `Idempotency-Key`

- Same key + same payload → `200` replay (`idempotent_replay: true`)
- Same key + different payload → `409` `IDEMPOTENCY_CONFLICT`

### Pricing

```
total = meal_price + box_charge
```

Snapshots: `meal_price`, `box_charge`, `total_price`, `currency=BDT`.

Delivery windows (Asia/Dhaka local): lunch `11:00`–`14:00`, dinner `19:30`–`22:30`.

### Eligibility reasons

| Code | Meaning |
|------|---------|
| `ACTIVE_SUBSCRIBER` | Has active subscription |
| `QUOTA_EXHAUSTED` | Lifetime accepted orders ≥ quota (Bengali message required) |

Unauthenticated callers receive `401`.

## Admin APIs

Base: `/api/v1/web/orders/test-meals/`  
Auth: verified admin.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/orders/` | List/search/filter |
| `GET` | `/orders/{public_id}/` | Detail |
| `POST` | `/orders/{public_id}/record-payment/` | Record or correct payment |
| `GET` | `/analytics/` | KPIs + chart series |

List filters: `service_date`, `date_from`/`date_to`, `meal_period`, `order_status`, `payment_status`, `package_public_id`, `zone_public_id`, `search`/`q`, `converted`.

### Revenue split (analytics)

| Field | Definition |
|-------|------------|
| `confirmed_order_value` | Sum of order totals in range |
| `collected_revenue` | Sum of `amount_collected` for paid orders |
| `outstanding_amount` | Sum of unpaid order totals |
| `delivered_unpaid_order_count` | Delivered + unpaid |

Primary conversion rate = after-delivery first subscribe customers / delivered Test Meal customers × 100 (0 when denominator is empty).

## Ops integration

- `meal_demand.get_demand` / kitchen requirement: additive `test_meal_count` (cancelled/failed excluded).
- Deliveryman board / today summary: `test_meal_quantity`; `total = regular + guest + test`.
- Admin dashboard: `test_meals_served` and consolidated total = regular + guest + test.
- Guest Meal and subscription wallet charge paths are unchanged.

## Error map

| HTTP | Typical codes |
|------|----------------|
| `401` | Unauthenticated |
| `403` | Not verified customer/admin |
| `404` | Other customer's order (customer detail) |
| `409` | `IDEMPOTENCY_CONFLICT` |
| `422` | `ACTIVE_SUBSCRIBER`, `QUOTA_EXHAUSTED`, `INVALID_DATE`, `CUTOFF_PASSED`, `PRICE_UNAVAILABLE`, `ADDRESS_NOT_FOUND`, … |

Body shape: `{ "detail": "...", "error_code": "..." }`.

## How to verify

```bash
python manage.py test orders.tests.test_test_meal
python manage.py test orders.tests.test_guest_meal orders.tests.test_meal_demand delivery_zones.tests.test_zone_based_delivery
```
