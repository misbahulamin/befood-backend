# Admin Wallet (Backend)

## Quick summary

BeFood’s **platform cash ledger** for verified admins. Separate from customer `wallet/`.

| Concern | Detail |
|--------|--------|
| App | `admin_wallet` |
| Base path | `/api/v1/web/admin-wallet/` |
| Auth | Token + `IsVerifiedAdmin` |
| Money | Decimal BDT, append-only ledger |
| Auto credit | Successful **customer wallet recharge** (custody) |
| Auto debit | Successful **customer wallet withdraw** (custody out); confirmed **inventory purchases** (`inventory_purchase`) |
| Meal revenue | Recognized from charged deliveries (does **not** cash-credit) |
| Inventory | See `inventory/docs/backend/admin-inventory.md` — purchase confirm debits wallet atomically with stock |

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin | Read summary/dashboard/history; deposit/withdraw/expense |
| Customer / anonymous | Denied (`401`/`403`) |

## Key models

- **AdminWallet** — singleton `code=platform`, denormalized `balance` + lifetime counters (`total_customer_funding`, `total_customer_withdrawals`, etc.).
- **AdminWalletTransaction** — append-only ledger (`type`, `direction`, `amount`, `balance_after`, source refs, `idempotency_key`).
- **AdminWalletAuditLog** — deposit / withdraw / expense / adjustment audit with previous/new balance.

## Ledger rules

1. All balance changes go through `credit_admin_wallet` / `debit_admin_wallet`.
2. Wallet row is locked with `select_for_update`.
3. Completed rows are immutable via API.
4. Idempotency key unique per wallet; replay returns original row.
5. `reconcile_balance()` must match stored balance to Σcredits − Σdebits.

## Custody accounting (current)

### Customer recharge → Admin Wallet credit

On successful **approved** customer recharge (`approve_recharge`):

- Credit type `customer_funding`, method `manual`
- Idempotency: `customer-recharge:{wallet_txn.public_id}`
- Same atomic block as customer credit on approve (pending submit does not credit)
- Flag: `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED` (default `True`)

### Customer withdraw → Admin Wallet debit

On successful **approved** customer withdraw (`approve_withdraw`):

- Debit type `customer_withdraw` (never mutates historical `customer_funding` credit rows)
- Idempotency: `customer-withdraw:{wallet_txn.public_id}`
- Pending withdraw create reserves customer **recharge** balance only (meal-stop capped at request); custody debit happens on approve
- Platform `balance` decreases; `total_customer_withdrawals` increases; **`total_customer_funding` is unchanged** (lifetime inflow counter)
- Summary/dashboard expose `net_customer_funding` = `max(0, total_customer_funding − total_customer_withdrawals)`
- If Admin Wallet float is insufficient at approve → `PlatformFloatError` → admin API `409`; request stays pending; reservation untouched
- Flag: same `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED` gates funding credit **and** withdraw debit (default `True` — keep on in production)

### Meal delivery charge → no cash credit

`charge_delivered_meal` debits the customer wallet only. It does **not** increase Admin Wallet balance (prepaid funds were already credited at recharge).

- Dashboard field `total_customer_payments` = sum of charged `OrderDelivery.charged_amount` (meal revenue recognition)
- Dashboard fields `total_profit` / `month_profit` = sum of published `MonthlyMenuSlot.profit_snapshot` for those charged deliveries (realized meal margin)
- Legacy flag `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` defaults to `False` (emergency rollback only; risks double-count)

```text
Customer recharges ৳500  → Admin Wallet +৳500 (customer_funding)
Meal charged ৳62         → Customer wallet −৳62; Admin cash unchanged
  (slot profit_snapshot ৳3.10 counts toward total_profit / month_profit)
Customer withdraws ৳100  → Admin Wallet −৳100 (customer_withdraw)
```

Customer withdraw is **custody liability release**, not business expense. It increments `total_customer_withdrawals` and MUST NOT increment `total_expenses` or decrease `total_customer_funding`. Dashboard `today_expense` / `month_expense` sum only `EXPENSE_TYPES`; use `today_customer_withdrawals` / `month_customer_withdrawals` for period custody outflows and `net_customer_funding` for remaining liability.

### Meal profit recognition

| Rule | Detail |
|------|--------|
| Source | Published menu slot `profit_snapshot` via `resolve_published_slot_for_delivery` |
| Scope | `OrderDelivery` with `payment_status=charged` and non-null `charged_amount` |
| Period axis | `OrderDelivery.updated_at` (same as meal revenue recognition) |
| Month window | Project `TIME_ZONE` calendar month (`_period_bounds_month`) |
| Missing slot/snapshot | Contributes `0.00` profit; dashboard still `200` |
| Not profit | `customer_funding`, manual deposits, or any Admin Wallet cash credit (`month_revenue`) |

Package drill-down: `profit_by_package.lifetime` / `.month` rows with `package_public_id`, `package_name`, `charged_deliveries`, `revenue`, `profit`. Sum of row `profit` equals the matching top-level field.

Implementation: `admin_wallet/services/profit.py` (`meal_profit_recognized`, `meal_profit_by_package`).

## Reconcile / cutover

```bash
# Pre-deploy accounting audit (read-only; exit 1 if live provider-ref duplicates)
python manage.py audit_wallet_accounting

# Preferred under custody accounting
python manage.py reconcile_admin_wallet_customer_funding --dry-run
python manage.py reconcile_admin_wallet_customer_funding

# LEGACY — do not use for cash backfill if funding credits are active
python manage.py reconcile_admin_wallet_meal_payments [--dry-run]
```

**Cutover warning:** If historical `customer_payment` meal cash credits already exist and you also backfill `customer_funding`, Admin Wallet balance can be inflated. Prefer forward-only funding from deploy; reverse/adjust old meal cash credits manually if needed.

## Endpoint grid

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/web/admin-wallet/` | Summary + lifetime totals |
| GET | `/api/v1/web/admin-wallet/dashboard/` | Today/month cards + recent txns |
| GET | `/api/v1/web/admin-wallet/transactions/` | Filtered history |
| GET | `/api/v1/web/admin-wallet/transactions/{public_id}/` | Detail |
| POST | `/api/v1/web/admin-wallet/deposits/` | Manual deposit |
| POST | `/api/v1/web/admin-wallet/withdrawals/` | Withdrawal |
| POST | `/api/v1/web/admin-wallet/expenses/` | Typed expense |
| GET | `/api/v1/web/admin-wallet/audit-logs/` | Audit trail |

Optional header on mutations: `Idempotency-Key`.

Filter `type` examples: `customer_funding`, `customer_withdraw`, `customer_payment` (legacy), `manual_deposit`, `inventory_purchase`, `inventory_purchase_reversal`, group `expense`.

### Inventory purchase debit

Service: `debit_for_inventory_purchase` / cancel via `credit_for_inventory_purchase_reversal`.

- Debit type `inventory_purchase`; idempotency `inventory-purchase:{purchase.public_id}`
- Credit type `inventory_purchase_reversal` on cancel (reduces `total_expenses`, not counted as income)
- Metadata / reference includes `inventory_purchase_public_id` for cross-navigation from Wallet → Inventory purchase

## How to verify

```bash
python manage.py test admin_wallet.tests.test_admin_wallet
python manage.py test orders.tests.test_meal_delivery_wallet_payment
```

OpenAPI tag: **Admin Wallet** (drf-spectacular).

## OpenSpec

`openspec/changes/admin-wallet-meal-profit-dashboard/`
`openspec/changes/admin-wallet-recharge-custody/`
