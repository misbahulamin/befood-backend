# Customer Wallet — Backend Notes

## Quick summary

The `wallet` app owns customer balances and an append-only ledger. Customer APIs are mounted at `/wallet/`. **Manual funding is admin-verified:** recharge/withdraw create `pending` requests; balance and Admin Wallet custody move only on admin approve (withdraw reserves spendable balance at submit).

| Endpoint | Auth | Notes |
|----------|------|-------|
| `GET /wallet/` | `IsVerifiedCustomer` | Lazy `get_or_create`; `min_wallet_balance_to_order` |
| `GET /wallet/transactions/` | same | Newest first, paginated |
| `GET /wallet/transactions/{public_id}/` | same | Ownership-scoped |
| `POST /wallet/recharge/` | same | Pending recharge (`bkash`/`nagad`/`bank` + `transaction_id`) |
| `POST /wallet/withdraw/` | same | Pending withdraw; reserves balance; `method=manual` |

Admin review (not gated by `WALLET_MANUAL_FUNDING_ENABLED`):

| Endpoint | Auth |
|----------|------|
| `GET /api/v1/web/wallet-funding/requests/` | `IsVerifiedAdmin` |
| `GET /api/v1/web/wallet-funding/requests/{public_id}/` | same |
| `POST .../approve/` | same |
| `POST .../reject/` | same (optional `reason`) |

Product labels: approved ≈ `completed`, rejected ≈ `failed`.

**Kill switch:** `WALLET_MANUAL_FUNDING_ENABLED=False` blocks **new** customer recharge/withdraw only. Admins can still resolve already-pending rows (critical for releasing reserved withdraws).

**Freeze:** Frozen wallets reject **new** customer funding. Admin approve/reject of already-pending rows remains allowed (including withdraw reservation release).

**Rollback warning:** Do **not** roll application code back to legacy instant withdraw while unresolved `pending` withdraw rows exist unless ops first approve/reject those reservations. Do not auto-delete pending rows. Nullable audit columns may remain after a code rollback.

---

## Permissions matrix

| Actor | Access |
|-------|--------|
| Anonymous | `401` |
| Unverified / non-customer | `403` via `IsVerifiedCustomer` |
| Verified customer | Own wallet only; funding create when kill switch on |
| Verified admin / superuser | Funding review APIs (`IsVerifiedAdmin`) |

---

## Models

### `Wallet`

- `OneToOne` → `CustomerProfile`
- `balance` `Decimal(12,2)` ≥ 0 — **spendable** (pending withdraw reservations already deducted)
- `currency` default `BDT`
- `status` `active` \| `frozen`

### `WalletTransaction`

| Field | Notes |
|-------|-------|
| `type` | `recharge`, `withdraw`, `payment`, … |
| `direction` | `credit` \| `debit` |
| `amount` | Positive decimal |
| `balance_after` | Snapshot after money move (null on pending recharge) |
| `status` | `pending`, `completed`, `failed`, `cancelled` |
| `method` | `manual`, `bkash`, `nagad`, `bank` |
| `external_ref` | Provider trx id for recharge (`transaction_id` in funding APIs) |
| `idempotency_key` | Unique per wallet when set |
| `reviewed_by` | FK → User (nullable); supports profile-less superusers |
| `reviewed_at` / `rejection_reason` | Audit |

Partial unique: provider-method recharge (`bkash|nagad|bank`) + non-empty `external_ref`.

---

## Funding flows

### Recharge

1. Customer posts `amount`, `payment_method`, `transaction_id` → pending credit, **no** balance change, admin email on commit.
2. Admin approve → credit customer + Admin Wallet custody + audit fields.
3. Admin reject → `failed`, no credit.

### Withdraw

1. Customer posts `amount` → pending debit, **immediate** spendable debit (`method=manual`), admin email on commit.
2. Admin approve → `completed` + Admin Wallet custody debit. Float shortfall → `409`, leave pending, review fields untouched.
3. Admin reject → restore reserved balance, `failed`.

### Lock order (approve/reject)

1. Funding `WalletTransaction` (`select_for_update`)
2. Customer `Wallet`
3. Admin Wallet via existing ingestion helpers

### Idempotency

- Lookup: `wallet + idempotency_key` only (type is fingerprint, not lookup).
- Same fingerprint → return existing txn with **current** status (`pending`/`completed`/`failed`); no new side effects/email.
- Conflicting fingerprint (incl. recharge vs withdraw same key) → `409`.

### HTTP errors (funding)

| Case | Status |
|------|--------|
| Invalid amount/method/blank trx id / insufficient balance | `400` |
| Unauthenticated | `401` |
| Forbidden / kill switch (customer create) | `403` |
| Not found | `404` |
| Duplicate provider ref / idempotency conflict / already processed / float shortfall | `409` |

---

## Service entry points

| Function | Role |
|----------|------|
| `request_recharge` / `request_withdraw` | Customer pending creates |
| `approve_recharge` / `reject_recharge` | Admin recharge resolution |
| `approve_withdraw` / `reject_withdraw` | Admin withdraw resolution |
| `credit_wallet` / `debit_wallet` | Core ledger helpers (meal payment, etc.) |
| `complete_pending_credit` / `fail_pending` | Low-level gateway seams (not funding approve API) |

Legacy `recharge_wallet` / `withdraw_wallet` remain in `ledger.py` for transitional callers but **must not** be used by customer APIs.
