## Context

Customer wallet funding today (`wallet.services.ledger.recharge_wallet` / `withdraw_wallet`) immediately completes ledger rows (`status=completed`, `method=manual`) and syncs Admin Wallet custody in the same atomic block. Models already reserve gateway-oriented fields (`status=pending|…`, `method=bkash|nagad`, `external_ref`) and low-level pending helpers, but customer APIs never create pending rows and there is no admin approve/reject surface or admin email fan-out for funding.

`IsVerifiedAdmin` / `is_verified_admin` treats active superusers as authorized even without an `AdminProfile`. Any `reviewed_by` design must be representable for every caller who can approve.

Stakeholders: customers, verified admins / superusers, frontend (payment instructions stay client-side), platform custody (`admin_wallet`).

Constraints: Decimal(12,2) money; reuse `Wallet` / `WalletTransaction`; reuse Django email; do not break meal `type=payment` debits or Admin Wallet ops APIs; no live payment gateway.

## Goals / Non-Goals

**Goals:**

- Manual-verification recharge/withdraw with `pending` → `completed` / `failed`.
- Funding-specific approve/reject services with audit, custody sync, and exactly-once side effects.
- Idempotency resolved before duplicate-ref / balance validation; concurrent same-key safety.
- Recharge-scoped provider-ref uniqueness; withdraw `method=manual`.
- Kill switch blocks only **new** customer submissions; admins can still resolve pending rows.
- Freeze blocks only **new** customer funding; admin resolution of existing pending rows remains allowed.
- Post-commit admin email with failure isolation and no resend on idempotent replay.
- Deterministic HTTP error contracts and separated customer/admin serializers.

**Non-Goals:**

- Live bKash/Nagad/Bank gateway / webhooks.
- Backend-hosted payment instruction / destination account config API.
- New mail provider.
- Changing Onahar, meal payment timing, or Admin Wallet inventory/ops APIs.
- Renaming ledger statuses to `approved`/`rejected`.
- Exposing reviewer identity on customer transaction APIs.

## Decisions

### 1. Reuse `WalletTransaction` as the funding request record

**Choice:** Pending/completed/failed recharge and withdraw rows stay on `WalletTransaction` (`type=recharge|withdraw`). No separate funding-request table.

**Rationale:** Existing fields cover lifecycle; avoids dual sources of truth.

**Alternatives considered:** Separate request table — deferred.

### 2. Status vocabulary: `pending` / `completed` / `failed`

**Choice:** Product “approved” = `completed`; “rejected” = `failed`. Store optional rejection text in `rejection_reason`.

### 3. Recharge: pending credit without balance change until approve

**Choice:** Submit creates `type=recharge`, `direction=credit`, `status=pending`, `method` ∈ {`bkash`,`nagad`,`bank`}, `external_ref` = sanitized `transaction_id`. Balance unchanged until approve.

### 4. Withdraw: reserve by debiting spendable balance on create; method = `manual`

**Choice:** Submit creates `type=withdraw`, `direction=debit`, `status=pending`, **`method=manual`**, `external_ref=''`, and immediately reduces `Wallet.balance`. No customer-provided provider transaction id in this release. Approve finalizes + custody debit; reject restores reserved balance.

### 5. `transaction_id` (API) vs `external_ref` (model)

**Choice:** Funding-specific request/response contracts use `transaction_id`. Serializers map sanitized `transaction_id` ↔ `WalletTransaction.external_ref`. Generic existing transaction list/detail may keep `external_ref` for backward compatibility if already public; new funding-specific admin contracts prefer `transaction_id` and MUST NOT expose both names for the same value unless compatibility requires it.

### 6. Duplicate provider refs scoped to provider recharge methods

**Choice:** Partial unique constraint conceptually:

- `type = recharge`
- `method IN (bkash, nagad, bank)`
- non-empty `external_ref`
- unique `(method, external_ref)`

Scoping to provider methods keeps historical/internal `manual` recharge refs outside the uniqueness rule. Service-level duplicate check remains for the same provider-method scope; DB constraint is the concurrency-safe final protection. Do **not** uniquify all wallet transaction types by `(method, external_ref)`.

**Migration:** Preflight query for duplicate non-empty provider-method recharge `(method, external_ref)` pairs. If duplicates exist: ops must resolve (e.g. suffix/clear obsolete refs on non-canonical rows, or temporary data fix) before applying the constraint — migration MUST NOT silently corrupt history. Representative completed/manual rows without conflicting provider recharge refs remain valid.

### 7. Idempotency ordering and payload fingerprint

**Choice:** For recharge and withdraw create:

1. Authenticate; resolve customer from auth.
2. Normalize/sanitize payload (`amount`, recharge `payment_method`, recharge `transaction_id` → `external_ref`).
3. If idempotency key present, look up existing txn by **`wallet + idempotency_key` only** (do **not** include funding type in the lookup namespace — that matches the existing per-wallet unique `idempotency_key` constraint).
4. If found: compare fingerprint (which **includes** `type`). Same fingerprint → return that existing transaction with its **current persisted status** (`pending`, `completed`, or `failed`); **no** second row, **no** second reservation, **no** balance/custody mutation, **no** second admin email. Different fingerprint (including recharge vs withdraw on the same key, or different amount/method/ref) → `409 Conflict`.
5. If not found: continue with amount/method/ref/balance validation (including duplicate recharge ref and spendable balance).
6. Atomic ledger mutation for a new row only.

**Idempotency comparison includes:** `type` (`recharge`/`withdraw`), normalized amount, recharge payment method, sanitized recharge `external_ref`. **`note` is excluded** from the fingerprint.

**Why type is fingerprint, not lookup:** Because uniqueness is per wallet + key, a lookup that also filtered by type would miss a prior recharge when a withdraw reuses the same key, then fail at insert. Fingerprint comparison correctly yields `409` for cross-type key reuse.

**Replay after lifecycle transition:** If the original request was later approved or rejected, same-key same-fingerprint replay still returns the same `public_id` with the **current** status (`completed`/`failed`), not a stale fake `pending` create response.

**Concurrency:** Rely on existing per-wallet unique `idempotency_key` constraint + `select_for_update` / integrity-error handling so concurrent same-key creates apply effects once.

### 8. `reviewed_by` → User (nullable)

**Choice:** `reviewed_by` is a nullable FK to the project `User` model, not `AdminProfile`.

**Rationale:** `is_verified_admin` returns True for active superusers without requiring `AdminProfile`. Storing User avoids “authorized but unrepresentable reviewer” gaps. Admin serializers may still resolve display name/email from the User; customers do not receive reviewer identity.

**Rejected alternative:** Require `AdminProfile` for approve/reject — would diverge from existing `IsVerifiedAdmin` superuser bypass.

### 9. Kill switch: new submissions only

**Choice:** When `WALLET_MANUAL_FUNDING_ENABLED` is false:

- Customer `POST /wallet/recharge/` and `POST /wallet/withdraw/` are blocked (`403`).
- Verified admins MAY still list/detail/approve/reject already-pending funding requests (critical for releasing reserved withdraw balances).

### 10. Frozen wallet: block new; allow admin resolution of existing pending

**Choice:** Frozen wallet rejects **new** customer recharge/withdraw. After a request is already pending, verified-admin approve/reject remains allowed even if the wallet is later frozen — including withdraw reject (restore reservation) and recharge approve/reject.

**Policy:** Freeze blocks customer-originated funding activity; it does not freeze admin resolution of the funding queue.

### 11. Approve/reject side-effect idempotency

**Choice:** First valid approve/reject processes the pending row. A second approve/reject against a non-pending request returns **`409 Conflict`**. No requirement that the second call return the original `200`. Effects are exactly-once: no double credit/debit, no double custody move, no double reservation release. Use `transaction.atomic()` + `select_for_update`.

### 12. Deterministic HTTP error contracts

| Condition | Status |
|---|---|
| Invalid amount / decimals / unsupported method / blank transaction id | `400` |
| Insufficient spendable customer balance | `400` |
| Duplicate recharge provider transaction id | `409` |
| Idempotency key conflicting payload | `409` |
| Approve/reject already-processed request | `409` |
| Insufficient Admin Wallet float on withdraw approve | `409` |
| Funding request not found | `404` |
| Unauthenticated | `401` |
| Authenticated non-admin / unverified admin | `403` |
| Manual funding kill switch (customer create only) | `403` |

### 13. Customer vs admin serializers

**Customer funding-visible fields (as applicable):** `public_id`, `type`, `direction`, `amount`, `status`, `method`, `transaction_id` (funding-specific) / compatible `external_ref` on generic history, `created_at`, `reviewed_at`, `rejection_reason`. **Do not** expose reviewer user/email/profile to customers.

**Admin serializers:** full audit including reviewer identity.

### 14. Post-commit admin email

**Choice:** Schedule notification with `transaction.on_commit` only when a **new** pending funding row is created. Callback catches/logs SMTP exceptions so email failure cannot turn a committed create into an HTTP error. Idempotent replay that returns an existing row MUST NOT schedule/send another email.

**Tests:** Use `captureOnCommitCallbacks(execute=True)` (or `TransactionTestCase`) so on-commit callbacks actually run.

### 15. Lock ordering (deadlock reduction)

**Choice:** Document and follow a consistent acquisition order inside funding approve/reject atomics, reusing existing Admin Wallet sync helpers:

1. Lock funding `WalletTransaction` (`select_for_update`)
2. Lock customer `Wallet` (`select_for_update`)
3. Perform customer balance mutation as required by the action
4. Call existing Admin Wallet ingestion/ledger helpers (which lock `AdminWallet` via their own `select_for_update`)

Do not invent a parallel Admin Wallet mutation path. Float shortfall must abort the entire atomic block with no partial commits.

### 16. Insufficient Admin Wallet float is fully non-mutating

**Choice:** On withdraw approve with insufficient float: return `409`; request stays `pending`; customer reservation remains; no Admin Wallet debit; `reviewed_by` / `reviewed_at` / `rejection_reason` unchanged. Do **not** auto-reject. Admin may retry later or explicitly reject.

### 17. Funding-specific service entrypoints

**Choice:** Public funding business API is:

- `request_recharge` / `request_withdraw`
- `approve_recharge` / `reject_recharge`
- `approve_withdraw` / `reject_withdraw`

Low-level ledger helpers may exist internally. Do **not** treat `complete_pending_credit` as the externally callable funding approval API. Customer views MUST NOT call legacy immediate-complete `recharge_wallet` / `withdraw_wallet`.

### 18. Amount limits apply to withdraw

**Choice:** Withdraw uses the same shared `validate_amount` / configured maximum as recharge, plus `amount <= spendable Wallet.balance`.

### 19. Admin APIs under web wallet-funding routes

**Choice:** `wallet/api/web_urls.py` at `api/v1/web/wallet-funding/` with `IsVerifiedAdmin`:

- `GET /requests/` (filter `type`, `status`, pagination)
- `GET /requests/{public_id}/`
- `POST /requests/{public_id}/approve/`
- `POST /requests/{public_id}/reject/` (optional `reason`)

### 20. Email recipients

**Choice:** Active verified admins (`AdminProfile.is_verified` + ADMIN group) plus active superusers with a usable email (aligned with permission model).

## Risks / Trade-offs

- [Breaking customer contract] → Docs + frontend contract; pending ≠ balance update for recharge.
- [Pending withdraw reduces displayed balance] → Document as reservation via spendable balance.
- [Float checked at approve] → `409` non-mutating; ops can top up float and retry.
- [Historical duplicate recharge refs] → Preflight + ops cleanup before unique constraint.
- [Rollback while pending withdraws exist] → Explicitly forbidden without reservation resolution (see Migration Plan).
- [Email gaps] → Log + admin list remains source of truth.

## Migration Plan

1. Add `Method.BANK`; `reviewed_by` → User null FK; `reviewed_at`; `rejection_reason`.
2. Preflight: detect duplicate non-empty provider-method recharge `(method, external_ref)` for `bkash|nagad|bank`; resolve before applying partial unique constraint scoped to those rows.
3. Add/review indexes for admin filters (`type`, `status`, `-created_at`).
4. Deploy migration (non-destructive to historical completed/manual rows without conflicting recharge refs).
5. Ship services + APIs + emails together.
6. **Rollback safety:** Application code may roll back while leaving nullable audit columns. **MUST NOT** roll back to legacy instant funding while unresolved `pending` withdraw rows exist unless ops first approve/reject (or otherwise restore) those reservations. Do **not** auto-delete pending funding rows on rollback.

## Open Questions

None blocking implementation; defaults above are normative for this change:

- Float shortfall → leave pending + `409` (non-mutating).
- Superusers without `AdminProfile` → may approve; stored on `reviewed_by` User FK; included in email recipients when email present.
- Amount max → existing shared validator for both recharge and withdraw.
- `note` → excluded from idempotency fingerprint.
