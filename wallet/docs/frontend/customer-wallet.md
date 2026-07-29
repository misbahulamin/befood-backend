# Customer Wallet — Frontend Integration

## Summary

Authenticated verified customers can view their wallet balance, browse ledger history, recharge (manual credit), and withdraw (manual debit). Live bKash/Nagad gateways are **not** integrated yet; the server always sets `method=manual` for funding APIs.

**Base path:** `/wallet/`  
**Auth:** `Authorization: Token <token>`  
**Permission:** verified customer (`CUSTOMER` group + email verified)  
**Identity:** use `public_id` (UUID) only — never integer database IDs

---

## Endpoint grid

| Method | Path | Why |
|--------|------|-----|
| `GET` | `/wallet/` | Show balance / status; creates wallet on first call |
| `GET` | `/wallet/transactions/` | Paginated history (newest first) |
| `GET` | `/wallet/transactions/{public_id}/` | Single transaction detail |
| `POST` | `/wallet/recharge/` | Add money (manual, immediate) |
| `POST` | `/wallet/withdraw/` | Reduce balance (manual, immediate) |

---

## Recommended UI flow

1. After login, call `GET /wallet/` to render balance.
2. Optionally load `GET /wallet/transactions/?page=1` for history.
3. Recharge screen → `POST /wallet/recharge/` with amount.
4. Withdraw screen → `POST /wallet/withdraw/` with amount (ensure UI checks balance first; server still enforces).
5. On flaky networks, send `Idempotency-Key` (UUID) so retries do not double-apply.

---

## Money format

- Amounts are decimal strings with **at most 2 decimal places** (e.g. `"500.00"`).
- Currency is currently always `BDT`.
- Min amount: `0.01`. Max amount: `100000.00`.
- Do **not** use floating-point math for display totals; treat API strings as source of truth.

---

## UUID rules

- Wallet and transactions expose `public_id` only.
- Transaction detail URLs use `public_id`, not numeric `id`.
- Looking up another customer’s transaction `public_id` returns `404` (not `403`).

---

## Auth headers

```http
Authorization: Token <your_token>
Content-Type: application/json
Idempotency-Key: <optional-uuid-for-funding>
```

Optional: body field `idempotency_key` is accepted if the header is omitted. Header wins when both are present.

---

## Examples

### GET wallet (first access creates zero balance)

```http
GET /wallet/
Authorization: Token ...
```

```json
{
  "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "balance": "0.00",
  "currency": "BDT",
  "status": "active",
  "min_wallet_balance_to_order": "500.00",
  "created_at": "2026-07-27T10:00:00.000000+06:00",
  "updated_at": "2026-07-27T10:00:00.000000+06:00"
}
```

`min_wallet_balance_to_order` is the admin-configured floor required before placing a meal package order (eligibility only — order create does not debit the wallet). See [`orders/docs/frontend/order-eligibility-wallet-min-balance.md`](../../orders/docs/frontend/order-eligibility-wallet-min-balance.md).

### POST recharge

```http
POST /wallet/recharge/
Authorization: Token ...
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "amount": "500.00",
  "note": "Cash top-up"
}
```

```json
{
  "wallet": {
    "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "balance": "500.00",
    "currency": "BDT",
    "status": "active",
    "created_at": "...",
    "updated_at": "..."
  },
  "transaction": {
    "public_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "type": "recharge",
    "direction": "credit",
    "amount": "500.00",
    "balance_after": "500.00",
    "status": "completed",
    "method": "manual",
    "note": "Cash top-up",
    "created_at": "...",
    "updated_at": "..."
  }
}
```

### POST withdraw

```http
POST /wallet/withdraw/
Authorization: Token ...
Content-Type: application/json

{
  "amount": "100.00"
}
```

Successful response mirrors recharge shape with `type=withdraw`, `direction=debit`, and decreased `balance`.

### List transactions

```http
GET /wallet/transactions/?page=1&page_size=20
```

Paginated (`count`, `next`, `previous`, `results`). Default page size 20, max 50.

---

## Field meanings (funding request)

| Field | Required | Meaning |
|-------|----------|---------|
| `amount` | yes | Positive decimal ≤ 2 dp, ≤ 100000.00 |
| `note` | no | Short operator/customer note |
| `idempotency_key` | no | Same as header; unique per wallet |

Clients **must not** send `method` (bKash/Nagad). Server sets `manual`.

---

## Errors (UI hints)

| Status | When | UI suggestion |
|--------|------|----------------|
| `401` | Missing/invalid token | Send to login |
| `400` | Invalid amount, frozen wallet, insufficient funds | Show `detail` / field errors |
| `403` | Not verified customer, or manual funding disabled | Block action / show support message |
| `404` | Unknown or foreign transaction `public_id` | Treat as missing |
| `409` | Same idempotency key, different amount | Generate a new key |

---

## Manual vs future bKash / Nagad

| Today | Later |
|-------|-------|
| `method=manual`, `status=completed` immediately | Customer may start a gateway session → `pending` → webhook completes |
| No provider credentials required | `payments` webhooks will call wallet ledger helpers |
| Withdraw reduces ledger only (no cash rail) | Real payout rail will attach later |

Do not hard-code UI copy that says “paid via bKash” for these endpoints until gateway APIs ship.

---

## Target clients

Mobile and web customer apps.
