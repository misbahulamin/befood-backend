# Admin Wallet — Frontend Integration

## Summary

Admin Panel **Wallet** section for BeFood platform cash: balance cards, transaction history, manual deposit/withdraw, and typed expenses. Web-only; requires verified admin JWT/Token.

**Base URL:** `/api/v1/web/admin-wallet/`  
**Auth header:** `Authorization: Token <token>`  
**Client:** web admin

## Recommended call order

1. `GET /dashboard/` — paint summary cards + recent table
2. `GET /transactions/?…` — full history with filters (on Wallet → History)
3. Mutations: `POST /deposits/`, `POST /withdrawals/`, `POST /expenses/`
4. Optional: `GET /audit-logs/` for compliance view
5. After any mutation, refresh `GET /` or `GET /dashboard/`

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| Wallet home / cards | GET | `/api/v1/web/admin-wallet/dashboard/` |
| Compact balance strip | GET | `/api/v1/web/admin-wallet/` |
| History table | GET | `/api/v1/web/admin-wallet/transactions/` |
| Transaction drawer | GET | `/api/v1/web/admin-wallet/transactions/{public_id}/` |
| Add money | POST | `/api/v1/web/admin-wallet/deposits/` |
| Withdraw | POST | `/api/v1/web/admin-wallet/withdrawals/` |
| Record expense | POST | `/api/v1/web/admin-wallet/expenses/` |
| Audit | GET | `/api/v1/web/admin-wallet/audit-logs/` |

## Dashboard response (field meanings)

```json
{
  "wallet": {
    "public_id": "uuid",
    "balance": "1500.00",
    "currency": "BDT",
    "status": "active",
    "total_received": "1500.00",
    "total_manual_added": "1500.00",
    "total_withdrawn": "0.00",
    "total_expenses": "0.00",
    "total_customer_payments": "0.00",
    "created_at": "…",
    "updated_at": "…"
  },
  "today_income": "0.00",
  "today_expense": "0.00",
  "month_revenue": "1500.00",
  "month_expense": "0.00",
  "total_customer_payments": "0.00",
  "total_withdrawn": "0.00",
  "recent_transactions": [ /* same shape as history rows */ ]
}
```

Suggested cards: **Current Balance**, **Today’s Income**, **Today’s Expense**, **This Month’s Revenue**, **This Month’s Expense**, **Total Customer Payments**, **Total Withdrawn**.

## Deposit

```http
POST /api/v1/web/admin-wallet/deposits/
Content-Type: application/json
Authorization: Token …
Idempotency-Key: optional-uuid

{
  "amount": "100000.00",
  "reason": "Seed capital",
  "note": "Q3 float"
}
```

**201** returns transaction object (`type=manual_deposit`, `direction=credit`).

## Withdrawal

```json
{
  "amount": "25000.00",
  "reason": "Operational Expense",
  "note": ""
}
```

Fails with **422** + `error_code: INSUFFICIENT_FUNDS` if amount &gt; balance. Always require reason in UI.

## Expense

```json
{
  "amount": "5000.00",
  "type": "rider_payment",
  "reason": "Weekly rider settlement",
  "note": "",
  "reference": "batch-42",
  "order_public_id": null,
  "customer_public_id": null
}
```

Allowlisted `type` values (debit expenses):

- `customer_refund`
- `restaurant_settlement`
- `rider_payment`
- `operational_expense`
- `onahar_expense`
- `promotional_cost`
- `platform_expense`
- `manual_adjustment`

## Transaction history filters

Query params (only these; others → **400**):

| Param | Example | Notes |
|-------|---------|-------|
| `date_from` / `date_to` | `2026-08-01` | Date inclusive |
| `direction` | `credit` \| `debit` | |
| `type` | `customer_payment` or group `expense` / `refund` | |
| `method` | `manual` \| `wallet` \| `bkash` \| `nagad` \| `other` | |
| `status` | `completed` | |
| `q` | uuid / email / order id | Search |
| `page` / `page_size` | | Max 100 |

### History row fields

`public_id`, `type`, `direction`, `amount`, `balance_after`, `status`, `method`, `source`, `reference`, `reason`, `note`, `order_public_id`, `delivery_public_id`, `customer_public_id`, `customer_email`, `admin_email`, `created_at`, `updated_at`.

Display tip: `+৳{amount} | {source} | {reference}`.

## Errors

```json
{
  "success": false,
  "message": "Insufficient admin wallet balance.",
  "errors": {},
  "error_code": "INSUFFICIENT_FUNDS"
}
```

| Code | When |
|------|------|
| `401` | Missing/invalid token |
| `403` | Not verified admin |
| `400` | Unsupported filter |
| `422` | Business validation (amount, funds, reason) |
| `404` | Unknown transaction |

## UI states

- Empty ledger: balance `0.00`, empty recent list — show deposit CTA.
- Frozen wallet (`status=frozen`): disable mutations; show banner (mutations will fail).
- After meal deliveries are marked delivered elsewhere, refresh dashboard to see `customer_payment` credits.
