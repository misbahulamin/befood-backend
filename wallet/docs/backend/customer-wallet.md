# Customer Wallet — Backend Notes

## Quick summary

The `wallet` app owns customer balances and an append-only ledger. Customer APIs are mounted at `/wallet/`. Manual recharge/withdraw credit/debit immediately; gateway completion helpers are reserved for future `payments` webhooks.

| Endpoint | Auth | Notes |
|----------|------|-------|
| `GET /wallet/` | `IsVerifiedCustomer` | Lazy `get_or_create` wallet; includes read-only `min_wallet_balance_to_order` from `OrderWalletSettings` |
| `GET /wallet/transactions/` | same | Newest first, paginated |
| `GET /wallet/transactions/{public_id}/` | same | Ownership-scoped |
| `POST /wallet/recharge/` | same | Manual completed credit |
| `POST /wallet/withdraw/` | same | Manual completed debit |

Order create eligibility (month lock + wallet minimum) is enforced in `orders.services.order_service.create_meal_order` and does **not** debit the wallet. See `orders/docs/backend/order-eligibility-wallet-min-balance.md`.

---

## Permissions matrix

| Actor | Access |
|-------|--------|
| Anonymous | `401` |
| Unverified / non-customer | `403` via `IsVerifiedCustomer` |
| Verified customer | Own wallet only |
| Django admin | Read-oriented inspection; balance/completed amounts not freely editable |

---

## Models

### `Wallet`

- `OneToOne` → `CustomerProfile` (`related_name='wallet'`)
- `balance` `Decimal(12,2)` ≥ 0
- `currency` default `BDT`
- `status` `active` \| `frozen`
- `PublicIdMixin` + timestamps

Balance **must** change only through `wallet.services.ledger`.

### `WalletTransaction` (append-only ledger)

| Field | Notes |
|-------|-------|
| `type` | `recharge`, `withdraw`, reserved: `payment`, `refund`, `adjustment` |
| `direction` | `credit` \| `debit` |
| `amount` | Positive decimal |
| `balance_after` | Snapshot after completed money move |
| `status` | `pending`, `completed`, `failed`, `cancelled` |
| `method` | `manual`, `bkash`, `nagad` |
| `idempotency_key` | Unique per wallet when set |
| `external_ref` | Future gateway reference |
| `metadata` | JSON bag for provider payloads later |

---

## Ledger invariants

1. Every completed balance change writes a ledger row.
2. Credit/debit use `transaction.atomic()` + `select_for_update()` on the wallet row.
3. Debit rejects when `amount > balance` (`InsufficientFundsError`).
4. Frozen wallets reject credit/debit (`WalletFrozenError`).
5. Balance never goes negative.
6. Customer APIs never mutate completed monetary fields.

---

## Service entry points

| Function | Role |
|----------|------|
| `get_or_create_wallet(profile)` | Provision zero-balance wallet |
| `validate_amount(amount)` | Positive, ≤2 dp, ≤ max cap |
| `credit_wallet` / `debit_wallet` | Core ledger + balance update |
| `recharge_wallet` / `withdraw_wallet` | Manual funding (+ idempotency) |
| `complete_pending_credit(txn)` | Gateway seam (pending → completed credit) |
| `fail_pending(txn)` | Gateway seam (pending → failed, no balance change) |

Settings flag: `WALLET_MANUAL_FUNDING_ENABLED` (env / `core.settings.base`, default `True`). When `False`, recharge/withdraw raise `ManualFundingDisabledError` → API `403`.

---

## Concurrency

Funding and ledger paths lock the wallet row before reading balance. Concurrent withdraws cannot overdraw. Idempotency keys are unique per wallet (`UniqueConstraint` with nulls allowed).

---

## Gateway seam (no live providers)

Customer recharge/withdraw **do not** accept `method=bkash|nagad`. Future flow:

1. Create `WalletTransaction` with `status=pending`, `method=bkash|nagad`, `external_ref=...` (from `payments`).
2. On success webhook → `complete_pending_credit(txn)`.
3. On failure → `fail_pending(txn)`.

Do not fake gateway success in customer APIs.

---

## Admin

- `WalletAdmin`: balance readonly; discourage raw edits.
- `WalletTransactionAdmin`: add/delete disabled; monetary fields readonly.

---

## How to verify

```bash
python manage.py test wallet.tests.test_basic
```

Manual Swagger (`/api/docs/`):

1. Authenticate as verified customer (Token).
2. `GET /wallet/` → balance `0.00`.
3. `POST /wallet/recharge/` `{"amount":"500.00"}` → balance `500.00`.
4. `POST /wallet/withdraw/` `{"amount":"100.00"}` → balance `400.00`.
5. `GET /wallet/transactions/` → newest first.
6. Replay recharge with same `Idempotency-Key` → same `transaction.public_id`, balance unchanged.

OpenSpec change: `openspec/changes/add-customer-wallet/`.
