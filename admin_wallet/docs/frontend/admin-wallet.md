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
- **Meal profit** (`total_profit` / `month_profit`) is realized margin from published slot `profit_snapshot` — **not** the same as `month_revenue` (cash credits).

## Recommended call order

1. `GET /dashboard/` — paint summary cards + recent table (**includes profit cards + package breakdown**)
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
    "net_customer_funding": "500.00",
    "created_at": "…",
    "updated_at": "…"
  },
  "today_income": "500.00",
  "today_expense": "0.00",
  "today_customer_withdrawals": "0.00",
  "month_revenue": "1500.00",
  "month_expense": "0.00",
  "month_customer_withdrawals": "0.00",
  "total_customer_payments": "62.00",
  "total_customer_funding": "500.00",
  "total_customer_withdrawals": "0.00",
  "net_customer_funding": "500.00",
  "total_withdrawn": "0.00",
  "total_profit": "3.10",
  "month_profit": "3.10",
  "profit_by_package": {
    "lifetime": [
      {
        "package_public_id": "uuid",
        "package_name": "Student",
        "charged_deliveries": 1,
        "revenue": "62.00",
        "profit": "3.10"
      }
    ],
    "month": [
      {
        "package_public_id": "uuid",
        "package_name": "Student",
        "charged_deliveries": 1,
        "revenue": "62.00",
        "profit": "3.10"
      }
    ]
  },
  "recent_transactions": [ /* same shape as history rows */ ]
}
```

| Field | UI meaning |
|-------|------------|
| `balance` | Current platform cash |
| `today_income` / `month_revenue` | Cash credits in period (includes `customer_funding` + manual deposits). **Not meal profit.** |
| `today_expense` / `month_expense` | **BREAKING semantics:** business `EXPENSE_TYPES` only (ops/onahar/promo/platform/inventory purchase/etc.). Does **not** include `customer_withdraw` or admin `withdrawal`. |
| `today_customer_withdrawals` / `month_customer_withdrawals` | Period custody outflows (`customer_withdraw`) — show separately from Expense cards |
| `total_customer_funding` | Lifetime customer recharge custody **in** (does **not** fall on withdraw) |
| `total_customer_withdrawals` | Lifetime customer withdraw custody **out** |
| `net_customer_funding` | Remaining customer custody liability: `max(0, funding − withdrawals)` — use this as “funding left” |
| `total_customer_payments` | **Meal revenue recognized** (charged deliveries), not cash-in from recharge |
| `total_profit` | **Lifetime realized meal profit** (Σ published slot `profit_snapshot` on charged deliveries) |
| `month_profit` | **This month** realized meal profit (same recognition; `updated_at` in current calendar month) |
| `profit_by_package.lifetime` | Package rows for the Total Profit card drill-down |
| `profit_by_package.month` | Package rows for the This Month Profit card drill-down |
| `total_withdrawn` | Admin-initiated withdrawals |

Suggested cards: **Current Balance**, **Today’s Income**, **Today’s Expense** (business only), **Today’s Customer Withdrawals**, **This Month’s Cash In**, **This Month’s Expense**, **This Month’s Customer Withdrawals**, **Meal Revenue (recognized)**, **Total Profit**, **This Month Profit**, **Customer Funding (lifetime)**, **Net Customer Funding**, **Total Withdrawn**.

Do **not** map customer withdraw approve to an Expense card — it reduces balance as custody settlement (`customer_withdraw`). Do **not** expect the lifetime Customer Funding counter to drop on withdraw; bind “funding remaining” to `net_customer_funding`.

### Customer wallet funding approve (panel)

For pending **customer** withdraw requests (`/api/v1/web/wallet-funding/`), show:

- Balance before / withdraw amount / remaining after reservation
- `meal_stop_threshold` context (customers cannot request below the floor on new submits)

See `wallet/docs/frontend/manual-wallet-funding.md`.

### Profit cards UX (Admin Panel `/admin/wallet`)

1. Render **Total Profit** from `total_profit` and **This Month Profit** from `month_profit`.
2. On card click, open a modal/drawer listing the matching array:
   - Total Profit → `profit_by_package.lifetime`
   - This Month Profit → `profit_by_package.month`
3. Table columns: package name, charged deliveries, revenue, profit (BDT decimal strings).
4. **Do not** bind profit cards to `month_revenue` — that field is cash income (funding + deposits).
5. No second API call needed for v1; breakdown ships in the same `GET /dashboard/` response.

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
- Meal deliveries with published slot profit increase **Total Profit** / **This Month Profit**; click those cards for package breakdown from `profit_by_package`.
- Customer funding / `month_revenue` must never be shown as profit.
