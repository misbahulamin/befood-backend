# Admin Test Meals — Admin Panel Integration

Backend contracts for the React Admin Panel. No Admin Panel code ships in this change.

## Auth

- Verified admin (`IsVerifiedAdmin`)
- Base: `/api/v1/web/orders/test-meals/`

## Screens

1. **Order list** — filters, search, pagination
2. **Order detail** — fulfillment + payment fields + conversion flags
3. **Record / correct payment** — audit trail
4. **Analytics** — KPIs + chart series

## List

`GET /api/v1/web/orders/test-meals/orders/`

Query params:

| Param | Notes |
|-------|-------|
| `service_date` | Exact `YYYY-MM-DD` |
| `date_from` / `from`, `date_to` / `to` | Range |
| `meal_period` | `lunch` \| `dinner` |
| `order_status` | `confirmed`, `preparing`, `out_for_delivery`, `delivered`, `cancelled`, `failed` |
| `payment_status` | `unpaid`, `paid`, `refunded` |
| `package_public_id` | UUID |
| `zone_public_id` | UUID |
| `converted` | `true`/`false` → historical subscribe-after-test |
| `search` / `q` | Name, phone, email, order public id |
| `page`, `page_size` | Default 20, max 100 |

Response: paginated `results` of admin order payloads (customer name/phone, package, slot, windows, address/zone, prices, statuses, conversion flags).

Customers calling this endpoint receive `401`/`403`.

## Detail

`GET /api/v1/web/orders/test-meals/orders/{public_id}/`

## Record payment

`POST /api/v1/web/orders/test-meals/orders/{public_id}/record-payment/`

```json
{
  "amount": "69.84",
  "collected_at": "2026-11-17T12:00:00Z",
  "notes": "Cash collected by rider"
}
```

- Omit `amount` to collect full `total_price`.
- Already-paid orders are idempotent (no second revenue count).
- Recording payment **does not** change `order_status`.
- To correct/refund, send `payment_status` (`paid` \| `unpaid` \| `refunded`) with optional amount/notes — creates an audit `TestMealPaymentEvent`.

## Analytics

`GET /api/v1/web/orders/test-meals/analytics/?date_from=2026-11-01&date_to=2026-11-30`

Key fields:

| Field | Meaning |
|-------|---------|
| `confirmed_order_value` | Sum of order totals |
| `collected_revenue` | Paid `amount_collected` sum |
| `outstanding_amount` | Unpaid totals |
| `unpaid_order_count` / `paid_order_count` | Counts |
| `delivered_unpaid_order_count` | Delivered but unpaid |
| `delivered_customer_count` | Denominator for primary conversion |
| `after_delivery_converted_customer_count` | Primary numerator |
| `pre_delivery_subscribed_customer_count` | Separate split |
| `primary_conversion_rate` | Percent; `0` when no delivered customers |
| `daily_series` | Chart rows (`date`, `orders`, `confirmed_value`, `deliveries`, …) |
| `package_popularity` | Package breakdown |
| `period_distribution` | Lunch/dinner counts |
| `revenue_notes` | Human definitions for UI footnotes |

## Display rules

- Keep payment badge independent of delivery badge (delivered + unpaid is valid).
- Distinguish `has_subscribed_after_test` (historical) vs `is_currently_active_subscriber`.
- Settings for box price / lifetime quota live on order-wallet-settings (`test_meal_box_price`, `test_meal_lifetime_quota`), not on this resource.
