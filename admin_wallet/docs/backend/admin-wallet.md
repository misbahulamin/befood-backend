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

- Debit type `customer_withdraw`
- Idempotency: `customer-withdraw:{wallet_txn.public_id}`
- Pending withdraw create reserves customer balance only; custody debit happens on approve
- If Admin Wallet float is insufficient at approve → `PlatformFloatError` → admin API `409`; request stays pending; reservation untouched

### Meal delivery charge → no cash credit

`charge_delivered_meal` debits the customer wallet only. It does **not** increase Admin Wallet balance (prepaid funds were already credited at recharge).

- Dashboard field `total_customer_payments` = sum of charged `OrderDelivery.charged_amount` (meal revenue recognition)
- Legacy flag `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` defaults to `False` (emergency rollback only; risks double-count)

```text
Customer recharges ৳500  → Admin Wallet +৳500 (customer_funding)
Meal charged ৳62         → Customer wallet −৳62; Admin cash unchanged
Customer withdraws ৳100  → Admin Wallet −৳100 (customer_withdraw)
```

## Reconcile / cutover

```bash
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

`openspec/changes/admin-wallet-recharge-custody/`
