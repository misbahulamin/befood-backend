# Admin Wallet — Frontend Integration

## Summary

Admin Panel **Wallet** section for BeFood platform cash: balance cards, transaction history, manual deposit/withdraw, and typed expenses. Web-only; requires verified admin JWT/Token.

**Base URL:** `/api/v1/web/admin-wallet/`  
**Auth header:** `Authorization: Token <token>`  
**Client:** web admin

**Accounting model (important):**

- Customer **recharge** increases Admin Wallet cash (`type=customer_funding`).
- Customer **withdraw** decreases Admin Wallet cash (`type=customer_withdraw`).
- Meal delivery charges do **not** increase Admin Wallet cash; `total_customer_payments` is recognized meal revenue from charged deliveries.

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
    "total_manual_added": "1000.00",
    "total_withdrawn": "0.00",
    "total_expenses": "0.00",
    "total_customer_payments": "62.00",
    "total_customer_funding": "500.00",
    "total_customer_withdrawals": "0.00",
    "created_at": "…",
    "updated_at": "…"
  },
  "today_income": "500.00",
  "today_expense": "0.00",
  "month_revenue": "1500.00",
  "month_expense": "0.00",
  "total_customer_payments": "62.00",
  "total_customer_funding": "500.00",
  "total_customer_withdrawals": "0.00",
  "total_withdrawn": "0.00",
  "recent_transactions": [ /* same shape as history rows */ ]
}
```

| Field | UI meaning |
|-------|------------|
| `balance` | Current platform cash |
| `today_income` / `month_revenue` | Cash credits in period (includes `customer_funding` + manual deposits) |
| `total_customer_funding` | Lifetime customer recharge custody in |
| `total_customer_withdrawals` | Lifetime customer withdraw custody out |
| `total_customer_payments` | **Meal revenue recognized** (charged deliveries), not cash-in from recharge |
| `total_withdrawn` | Admin-initiated withdrawals |

Suggested cards: **Current Balance**, **Today’s Income**, **Today’s Expense**, **This Month’s Cash In**, **This Month’s Expense**, **Meal Revenue (recognized)**, **Customer Funding**, **Total Withdrawn**.

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
- `inventory_purchase` (created by Inventory confirm — prefer Inventory UI; see `inventory/docs/frontend/admin-inventory.md`)

Related credit type from inventory cancel: `inventory_purchase_reversal`.  
Wallet history rows for inventory include `reference` like `Purchase #{uuid}` and metadata `inventory_purchase_public_id` — use that to deep-link to Inventory purchase detail.

## Transaction history filters

Query params (only these; others → **400**):

| Param | Example | Notes |
|-------|---------|-------|
| `date_from` / `date_to` | `2026-08-01` | Date inclusive |
| `direction` | `credit` \| `debit` | |
| `type` | `customer_funding`, `customer_withdraw`, `inventory_purchase`, `inventory_purchase_reversal`, `customer_payment` (legacy), or group `expense` / `refund` | |
| `method` | `manual` \| `wallet` \| `bkash` \| `nagad` \| `other` | |
| `status` | `completed` | |
| `q` | uuid / email / order id | Search |
| `page` / `page_size` | | Max 100 |

### History row fields

`public_id`, `type`, `direction`, `amount`, `balance_after`, `status`, `method`, `source`, `reference`, `reason`, `note`, `order_public_id`, `delivery_public_id`, `customer_public_id`, `customer_email`, `admin_email`, `created_at`, `updated_at`.

Display tip: `+৳{amount} | {source} | {reference}`.

Common custody types:

| `type` | Direction | Meaning |
|--------|-----------|---------|
| `customer_funding` | credit | Customer recharged personal wallet |
| `customer_withdraw` | debit | Customer withdrew from personal wallet |
| `customer_payment` | credit | Legacy meal cash credit (should not appear for new meals) |
| `inventory_purchase` | debit | Food inventory purchase confirmed |
| `inventory_purchase_reversal` | credit | Inventory purchase cancelled |

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
- After customers recharge, refresh dashboard to see `customer_funding` credits and higher balance.
- Meal deliveries increase **Meal Revenue** (`total_customer_payments`), not cash balance.
