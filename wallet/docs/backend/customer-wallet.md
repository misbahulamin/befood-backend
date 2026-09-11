# Customer Wallet — Backend Notes

## Quick summary

The `wallet` app owns customer balances and an append-only ledger. Customer APIs are mounted at `/wallet/`. **Manual funding is admin-verified:** recharge/withdraw create `pending` requests; balance and Admin Wallet custody move only on admin approve (withdraw reserves spendable balance at submit).

### Dual balance buckets

| Field | Meaning |
|-------|---------|
| `balance` | Total spendable = `recharge_balance` + `commission_balance` |
| `recharge_balance` | Customer recharge/refund funds (full recharge bucket) |
| `withdrawable_balance` | **API computed:** `max(0, recharge_balance - meal_stop_threshold)` — maximum allowed withdraw |
| `commission_balance` | Referral commission; meal-spendable, **not** withdrawable |

Meal payment debits burn `commission_balance` first, then `recharge_balance`. Completed ledger rows store `balance_after`, `recharge_balance_after`, and `commission_balance_after` (must sum consistently).

Withdraw never spends commission. Shared helper: `wallet.services.withdrawable.compute_maximum_withdrawable`.

Ops: `python manage.py verify_wallet_balance_consistency` and `python manage.py audit_wallet_accounting`

Provider recharge external refs are unique among live (pending/completed) rows. Approving a recharge may set `meal_service_restored` when low-balance meal-stop clears.

| Endpoint | Auth | Notes |
|----------|------|-------|
| `GET /wallet/` | `IsVerifiedWalletCustomer` | Lazy `get_or_create`; thresholds + `withdrawable_balance` |
| `GET /wallet/transactions/` | same | Newest first, paginated |
| `GET /wallet/transactions/{public_id}/` | same | Ownership-scoped |
| `POST /wallet/recharge/` | same | Pending recharge (`bkash`/`nagad`/`bank` + `transaction_id`) |
| `POST /wallet/withdraw/` | same | Pending withdraw; reserves recharge only; meal-stop capped |

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
| Identity-unverified / non-customer | `403` via `IsVerifiedWalletCustomer` (detail: wallet identity message; phone **or** email **or** social satisfies identity) |
| Identity-verified customer (incl. phone-only) | Own wallet only; funding create when kill switch on |
| Verified admin / superuser | Funding review APIs (`IsVerifiedAdmin`) |

Phone OTP registration sets `is_phone_verified=True`; email verification is **not** required for wallet access.

---

## Models

### `Wallet`

- `OneToOne` → `CustomerProfile`
- `balance` `Decimal(12,2)` ≥ 0 — **spendable** (pending withdraw reservations already deducted)
- `recharge_balance` / `commission_balance` — dual buckets; `balance == recharge + commission`
- `withdrawable_balance` (computed property / API) — `max(0, recharge_balance - meal_stop_threshold)`
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

Partial unique: provider-method recharge (`bkash|nagad|bank`) + non-empty `external_ref` **only while status is `pending` or `completed`**. Failed/rejected (and cancelled) refs may be reused on a new request. Reject leaves `external_ref` unchanged for audit.

---

## Funding flows

### Recharge

1. Customer posts `amount`, `payment_method`, `transaction_id` → pending credit, **no** balance change, admin email on commit.
2. Admin approve → credit customer + Admin Wallet custody + audit fields; that `transaction_id` remains blocked.
3. Admin reject → `failed`, no credit; same `transaction_id` may be submitted again.

### Withdraw

1. Customer posts `amount` → must be `<= max(0, recharge_balance - meal_stop_threshold)`. Pending debit **immediately** reserves `recharge_balance` only (`method=manual`); commission untouched. Admin email on commit. **No** Admin Wallet debit yet.
2. Admin approve → `completed` + Admin Wallet custody debit type `customer_withdraw` (platform `balance` ↓, `total_customer_withdrawals` ↑). **Does not** decrease lifetime `total_customer_funding` or rewrite `customer_funding` credit rows. Float shortfall → `409`, leave pending, review fields untouched (full atomic rollback).
3. Admin reject → restore reserved recharge, `failed`.

**Production note:** Keep `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED=true` so approve posts `customer_withdraw`. Missing historical custody rows → ops `reconcile_admin_wallet_customer_funding` (idempotent); do not recalculate live balances.

Example: recharge `420`, meal_stop `100` → max withdraw `320`. After a `300` request, recharge left `120`.

### Pre-deploy audit

```bash
python manage.py audit_wallet_accounting
```

Must exit 0 (no live pending/completed provider-ref duplicates) before applying the uniqueness migration.

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
| Invalid amount/method/blank trx id / insufficient or over meal-stop max | `400` |
| Unauthenticated | `401` |
| Forbidden / kill switch (customer create) | `403` |
| Not found | `404` |
| Duplicate provider ref / idempotency conflict / already processed / float shortfall | `409` |

---

## Service entry points

| Function | Role |
|----------|------|
| `request_recharge` / `request_withdraw` | Customer pending creates (withdraw meal-stop capped) |
| `approve_recharge` / `reject_recharge` | Admin recharge resolution |
| `approve_withdraw` / `reject_withdraw` | Admin withdraw resolution + `customer_withdraw` custody |
| `compute_maximum_withdrawable` | Shared `recharge − meal_stop` formula |
| `credit_wallet` / `debit_wallet` | Core ledger helpers (meal payment, etc.) |
| `complete_pending_credit` / `fail_pending` | Low-level gateway seams (not funding approve API) |

Legacy `recharge_wallet` / `withdraw_wallet` remain in `ledger.py` for transitional callers but **must not** be used by customer APIs.
