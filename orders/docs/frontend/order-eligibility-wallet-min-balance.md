# Frontend: order eligibility (month lock + wallet minimum)

## Summary

Before creating a meal package order, the server checks:

1. Customer does **not** already have a non-cancelled package for that calendar month.
2. Wallet balance is at least the admin-configured **minimum** (default **500.00 BDT**).

This is an **eligibility** check only — placing an order does **not** deduct wallet balance.

**New / changed:**

- Admin: `GET|PATCH /api/v1/web/orders/order-wallet-settings/`
- Customer wallet: `GET /wallet/` includes `min_wallet_balance_to_order`
- Order create `400` may return insufficient-balance or frozen-wallet messages (in addition to month lock)

## Integration steps

### Admin panel — set minimum balance

1. Call `GET /api/v1/web/orders/order-wallet-settings/` with admin token.
2. Show editable field for `min_wallet_balance_to_order` (decimal string, 2 places).
3. Save with `PATCH` same URL and body `{ "min_wallet_balance_to_order": "600.00" }`.
4. Label clearly: “Minimum wallet balance required to place an order (BDT). Order create does not charge the wallet.”

### Customer app — before order CTA

1. Call `GET /wallet/` after login.
2. Read `balance`, `status`, and `min_wallet_balance_to_order`.
3. If `status === "frozen"`, disable order and explain wallet is frozen.
4. If `balance < min_wallet_balance_to_order`, prompt recharge (link to wallet recharge) instead of (or before) order submit.
5. Still handle server `400` — never rely on client checks alone.

### Customer app — order create errors

| Error text contains | UI |
|---------------------|-----|
| `already have a meal package for this month` | “You already have a package this month.” Hide/disable package switch. |
| `Insufficient wallet balance` | Show required vs current; CTA to recharge. |
| `wallet is frozen` | Support / wait messaging; do not offer recharge-only fix. |

## Auth / headers

```http
Authorization: Token <token>
Content-Type: application/json
```

Admin settings: verified admin. Order create & wallet GET: verified customer.

## Examples

### Wallet GET (customer)

```http
GET /wallet/
Authorization: Token <customer-token>
```

```json
{
  "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "balance": "250.00",
  "currency": "BDT",
  "status": "active",
  "min_wallet_balance_to_order": "500.00",
  "created_at": "2026-07-27T10:00:00.000000+06:00",
  "updated_at": "2026-07-27T10:00:00.000000+06:00"
}
```

### Admin patch minimum

```http
PATCH /api/v1/web/orders/order-wallet-settings/
Authorization: Token <admin-token>
Content-Type: application/json

{ "min_wallet_balance_to_order": "600.00" }
```

```json
{
  "min_wallet_balance_to_order": "600.00",
  "updated_at": "2026-07-29T12:00:00.000000+06:00"
}
```

### Order create — insufficient balance

```http
POST /orders/
Authorization: Token <customer-token>
Content-Type: application/json

{
  "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "customer_note": ""
}
```

```json
{
  "non_field_errors": [
    "Insufficient wallet balance to place an order. Minimum required is 500.00, current balance is 250.00."
  ]
}
```

### Order create — month lock

```json
{
  "non_field_errors": [
    "You already have a meal package for this month. You cannot change meal type within the same month."
  ]
}
```

## Edge cases

- Exact balance equal to minimum (e.g. `500.00` when min is `500.00`) **is allowed**.
- No wallet yet → treated as `0.00` until customer opens wallet / recharges.
- Cancelled package for the month → customer **can** order again.
- Changing admin minimum applies immediately to the next order create.
- Do **not** show “payment successful” or reduce displayed balance after order create from this gate.

## Target clients

- **Web admin:** settings screen for minimum balance
- **Mobile / web customer:** wallet + order screens using `min_wallet_balance_to_order` and error mapping
