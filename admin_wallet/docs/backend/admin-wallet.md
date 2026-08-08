# Admin Wallet (Backend)

## Quick summary

BeFood’s **platform cash ledger** for verified admins. Separate from customer `wallet/`.

| Concern | Detail |
|--------|--------|
| App | `admin_wallet` |
| Base path | `/api/v1/web/admin-wallet/` |
| Auth | Token + `IsVerifiedAdmin` |
| Money | Decimal BDT, append-only ledger |
| Auto credit | Successful meal-delivery customer charge |

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin | Read summary/dashboard/history; deposit/withdraw/expense |
| Customer / anonymous | Denied (`401`/`403`) |

## Key models

- **AdminWallet** — singleton `code=platform`, denormalized `balance` + lifetime counters.
- **AdminWalletTransaction** — append-only ledger (`type`, `direction`, `amount`, `balance_after`, source refs, `idempotency_key`).
- **AdminWalletAuditLog** — deposit / withdraw / expense / adjustment audit with previous/new balance.

## Ledger rules

1. All balance changes go through `credit_admin_wallet` / `debit_admin_wallet`.
2. Wallet row is locked with `select_for_update`.
3. Completed rows are immutable via API.
4. Idempotency key unique per wallet; replay returns original row.
5. `reconcile_balance()` must match stored balance to Σcredits − Σdebits.

## Meal-payment ingestion

On successful `charge_delivered_meal`:

- Credit type `customer_payment`, method `wallet`
- Idempotency: `meal-payment:{delivery.public_id}`
- Same atomic block as customer debit
- Flag: `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` (default `True`)

Customer wallet **recharge does not** credit Admin Wallet (avoids double-count).

Backfill: `python manage.py reconcile_admin_wallet_meal_payments [--dry-run]`

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

## How to verify

```bash
python manage.py test admin_wallet.tests.test_admin_wallet
python manage.py test orders.tests.test_meal_delivery_wallet_payment
```

OpenAPI tag: **Admin Wallet** (drf-spectacular).

## OpenSpec

`openspec/changes/admin-wallet-system/`
