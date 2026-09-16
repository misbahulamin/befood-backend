## Context

BeFood already runs dual-bucket customer wallets (`recharge_balance` withdrawable, `commission_balance` meal-spendable only) and Admin Wallet custody accounting:

- Recharge approve → Admin Wallet credit `type=customer_funding`
- Withdraw approve → Admin Wallet debit `type=customer_withdraw` via `debit_from_customer_withdraw` inside `approve_withdraw` (`transaction.atomic`)

Customer funds are reserved (recharge-only debit) at **request** time; Admin float moves only on **approve**. Lifetime counters `total_customer_funding` / `total_customer_withdrawals` are cumulative inflows/outflows — funding credits are never rewritten on withdraw.

Observed product gaps:

1. Operators expect “customer_funding balance” to shrink on withdraw. The platform **cash** balance already shrinks via `customer_withdraw`, but `total_customer_funding` does not (by design). This looks like a sync bug when panels only watch that counter.
2. `withdrawable_balance` currently equals full `recharge_balance` with no `meal_stop_threshold` floor, so customers can drain below meal-stop and risk meal service pause.

Stakeholders: customers (mobile/web), verified admins (approve + Admin Wallet dashboard), finance/ops.

## Goals / Non-Goals

**Goals:**

- Enforce `maximum_withdrawable = max(0, recharge_balance - meal_stop_threshold)` on withdraw request (and expose it on wallet summary).
- Keep withdraw debit strategy recharge-only; commission never withdrawable.
- Keep Admin Wallet custody sync on approve using existing `customer_withdraw` debit; verify atomicity and feature-flag behavior.
- Expose net custody (`total_customer_funding - total_customer_withdrawals`) so admin UI can show remaining customer funding liability without mutating historical credits.
- Document mobile, customer web, and admin approve UX (remaining balance / threshold messaging).
- Production-safe forward-only change: no historical ledger rewrite, no balance recalculation.

**Non-Goals:**

- Changing meal payment / commission-first debit strategy.
- Debiting or reversing historical `customer_funding` credit rows on withdraw.
- Recalculating existing customer or Admin Wallet balances.
- Building mobile/admin UI code in this backend repo (docs + API contract only).
- Changing `meal_stop_threshold` settings API itself (reuse `OrderWalletSettings`).

## Decisions

### 1. Keep `customer_withdraw` as custody outflow (do not debit `customer_funding` type)

- **Choice:** Continue posting Admin Wallet debit `type=customer_withdraw` on approve; reduce platform `balance`; increment `total_customer_withdrawals`.
- **Rationale:** `customer_funding` is a credit enum used for recharge inflow. Posting a debit with that type (or mutating old credit rows) breaks ledger semantics, expense exclusions, and reconcile idempotency keys already in production.
- **Alternatives considered:** (a) Reverse a `customer_funding` credit — rejected (history rewrite, non-idempotent pairing). (b) Debit with type `customer_funding` — rejected (type means credit category; filters/docs would break).

### 2. Net custody is derived, not a stored mutable “funding balance”

- **Choice:** Add/document `net_customer_funding = total_customer_funding - total_customer_withdrawals` on admin summary/dashboard (additive field).
- **Rationale:** Matches operator mental model (“funding left in custody”) without changing counters.
- **Alternatives considered:** Decrease `total_customer_funding` on withdraw — rejected (destroys lifetime inflow audit).

### 3. Withdrawable formula uses recharge bucket only

- **Choice:** `maximum_withdrawable = max(0, recharge_balance - meal_stop_threshold)`.
- **Rationale:** Commission is non-withdrawable; meal-stop protection must not allow draining recharge while leaving only commission (or vice versa) inconsistently. Product explicitly chose recharge − threshold over total balance − threshold.
- **Note:** This is slightly conservative when commission alone could keep total balance above meal-stop; accepted per product rule.
- **Alternatives considered:** `balance - meal_stop_threshold` — rejected by product; would allow commission-shaped withdrawals indirectly by freeing recharge.

### 4. Single shared helper for max withdrawable

- **Choice:** Centralize in wallet domain (e.g. `Wallet.withdrawable_balance` property and/or `compute_maximum_withdrawable(recharge_balance, meal_stop_threshold)` used by model, serializer, and `request_withdraw`).
- **Rationale:** Mobile, web, admin, and service validation must share one rule.

### 5. Validate at request time; approve keeps custody sync only

- **Choice:** Enforce meal-stop floor in `request_withdraw` before reservation. Approve continues to complete status + `_sync_admin_wallet_withdraw`. Do not re-apply meal-stop on approve for already-reserved pending rows created under old rules (avoid stuck approvals), unless remaining reserved amount still violates an explicit new guard we document — prefer grandfather pending.
- **Rationale:** Reservation already reduced `recharge_balance`; re-checking threshold against post-reservation balance would false-fail legitimate pending rows.

### 6. API field strategy

- **Choice:** Keep field name `withdrawable_balance` but change semantics to threshold-aware maximum. Also expose `meal_stop_threshold` (already present). Optionally alias `maximum_withdrawable` as the same value for clarity in docs; prefer one field to avoid duplication unless clients already need both names — document that `withdrawable_balance` **is** the maximum withdrawable.
- **Rationale:** WalletSerializer already returns `withdrawable_balance`; semantic change is **BREAKING** for clients that assumed full recharge, but matches product language.

### 7. Error contract

- **Choice:** Reject over-cap withdraw with `400`/`422` and a clear message including maximum and threshold (reuse existing funding error style / `InsufficientFundsError` or dedicated validation error).
- **Rationale:** Frontend shows friendly copy; backend remains source of truth.

## Risks / Trade-offs

- [Risk] Clients still send amounts based on old `withdrawable_balance` meaning → Mitigation: clear error detail; docs; optional response fields on wallet GET already include threshold.
- [Risk] Operators still look only at `total_customer_funding` → Mitigation: add `net_customer_funding`; update admin frontend docs to map cards correctly.
- [Risk] Feature flag `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED` disables both funding credit and withdraw debit → Mitigation: document production must keep flag on; tests cover sync path when enabled.
- [Risk] Pending pre-change withdraws reserved below meal-stop → Mitigation: grandfather on approve; only new requests enforce floor.
- [Risk] Conservative recharge−threshold may block withdraws when total balance (with commission) is still healthy → Mitigation: accepted product trade-off; document in client docs.
- [Trade-off] Not rewriting history means past withdrawals that lacked Admin rows need reconcile command, not silent auto-rewrite in this change.

## Migration Plan

1. Deploy backend with meal-stop withdraw validation + updated `withdrawable_balance` semantics + optional `net_customer_funding`.
2. Confirm `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED=true` in production.
3. Optionally dry-run `reconcile_admin_wallet_customer_funding` for missing custody rows only (ops-owned; not automatic rewrite of balances).
4. Ship mobile/web/admin client updates reading new withdrawable meaning.
5. Rollback: revert deploy; pending reservations remain ledger-consistent; no data migration to undo.

## Open Questions

- None blocking: product confirmed formula `recharge_balance - meal_stop_threshold`.
- Whether to add literal response key `maximum_withdrawable` in addition to `withdrawable_balance` — default **no** (same value); document synonym in frontend docs unless a client explicitly needs the alias during rollout.
