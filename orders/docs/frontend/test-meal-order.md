# Test Meal — Flutter Integration

Backend-only contracts for the customer Test Meal funnel. No Flutter code ships in this change.

## Auth

- Header: `Authorization: Token <token>` (or project JWT equivalent)
- Role: verified customer (`CUSTOMER` group + identity verified)
- Base path: `/api/v1/test-meals/`

## Recommended flow

1. `GET /eligibility/` — gate CTA
2. If eligible → `GET /packages/`
3. User picks package + date + lunch/dinner → `POST /quote/`
4. User selects owned serviceable address (`customer/addresses` existing APIs)
5. `POST /orders/` with `Idempotency-Key`
6. Show confirmation + history via `GET /orders/` / `GET /orders/{public_id}/`
7. Optional: `POST /funnel-events/` for CTA clicks (never treat as an order)

## Endpoints

### Eligibility

`GET /api/v1/test-meals/eligibility/`

```json
{
  "eligible": true,
  "is_active_subscriber": false,
  "quota_limit": 2,
  "quota_used": 1,
  "quota_remaining": 1,
  "reason": null,
  "message_bn": null,
  "message_en": null,
  "currency": "BDT",
  "delivery_windows": {
    "lunch": {"start": "11:00", "end": "14:00"},
    "dinner": {"start": "19:30", "end": "22:30"}
  }
}
```

When ineligible, show `message_bn` (required for `QUOTA_EXHAUSTED`).

### Packages

`GET /api/v1/test-meals/packages/`

```json
[
  {
    "public_id": "…",
    "name": "Student Package",
    "meal_name": "Student Package"
  }
]
```

### Quote

`POST /api/v1/test-meals/quote/`

```json
{
  "service_date": "2026-11-17",
  "meal_period": "lunch",
  "package_public_id": "…"
}
```

Response includes `meal_price`, `box_charge`, `total_price`, delivery window. Quote does **not** create an order. Do not send client prices as authoritative on create.

### Create

`POST /api/v1/test-meals/orders/`  
Header: `Idempotency-Key: <uuid>`

```json
{
  "service_date": "2026-11-17",
  "meal_period": "lunch",
  "package_public_id": "…",
  "address_public_id": "…",
  "special_instructions": "Less spicy"
}
```

Success: `201` (or `200` with `idempotent_replay: true`).  
Order is `confirmed` + `unpaid` + `manual`. Wallet balance is unchanged.

### History

- `GET /api/v1/test-meals/orders/?page=1&page_size=20`
- `GET /api/v1/test-meals/orders/{public_id}/`

Other customers' orders return `404`.

### Funnel (optional)

`POST /api/v1/test-meals/funnel-events/`

```json
{
  "event_name": "cta_click",
  "client_event_id": "device-local-id",
  "correlation_id": "anon-session",
  "metadata": {}
}
```

Duplicates return `200` with `created: false`. Clicks never create orders.

## Error handling

| Status | `error_code` examples | UI hint |
|--------|------------------------|---------|
| `401` | — | Login |
| `403` | — | Verify account |
| `409` | `IDEMPOTENCY_CONFLICT` | Retry with new key |
| `422` | `ACTIVE_SUBSCRIBER`, `QUOTA_EXHAUSTED`, `CUTOFF_PASSED`, `INVALID_DATE`, `PRICE_UNAVAILABLE`, `ADDRESS_NOT_FOUND` | Show `detail` / `message_bn` |

```json
{
  "detail": "…",
  "error_code": "QUOTA_EXHAUSTED"
}
```

## UI states

- Hide Test Meal CTA when `eligible=false` (or show subscribe CTA with Bengali message).
- After create, payment remains unpaid until admin records cash — show “Pay on delivery / cash” style copy.
- Keep showing past Test Meal history after the user later subscribes.
