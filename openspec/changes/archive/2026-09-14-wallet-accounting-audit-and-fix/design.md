## Context

BeFood production already runs customer wallet funding (provider recharge + withdraw with admin review) and Admin Wallet custody sync. Two accounting inconsistencies are visible in production:

1. **Provider `transaction_id` reuse after reject** — `wallet.services.funding._provider_ref_taken` and DB constraint `wallet_txn_unique_provider_recharge_ref` treat any recharge row with the same `(method, external_ref)` as a duplicate, including `status=failed` after admin reject. Rejected rows keep `external_ref` unchanged and never credited the customer or Admin Wallet.
2. **Withdraw shown as “expense”** — Approve withdraw correctly posts Admin Wallet `type=customer_withdraw` and increments `total_customer_withdrawals` (not `total_expenses`). Dashboard `period_totals` nevertheless sets `expense` to the sum of **all** completed DEBIT rows, so UI cards labeled “Today’s / Month’s Expense” include customer custody payouts.

Constraints from stakeholders: no production history rewrite; no wallet architecture rewrite; keep recharge/withdraw/approval/notification flows intact except for these corrections; backend remains source of truth.

### Current flows (as-is)

```text
Recharge create → pending WalletTransaction (external_ref set)
  → Approve → completed + customer credit + Admin customer_funding
  → Reject  → failed + external_ref kept → blocks same trx id forever

Withdraw create → pending customer debit (reservation)
  → Approve → completed + Admin customer_withdraw debit (balance ↓)
  → Reject  → restore customer balance + failed
```

## Goals / Non-Goals

**Goals:**

- Allow reuse of provider `transaction_id` when no live (`pending`/`completed`) recharge holds that ref.
- Keep blocking reuse when a pending or completed recharge already owns the ref.
- Ensure Admin Wallet period “expense” means business `EXPENSE_TYPES` only.
- Keep withdraw approve as custody `customer_withdraw` with Admin balance reduction.
- Ship read-only production audit steps and regression tests before/with the fix.
- Document API semantic change for dashboard expense fields.

**Non-Goals:**

- Rewriting or deleting historical `WalletTransaction` / `AdminWalletTransaction` rows.
- Recalculating lifetime counters from scratch in an automatic migration.
- Adding a new ledger type when `customer_withdraw` already exists.
- Changing notification, invoice, or meal-stop resume behavior.
- Full wallet/admin-wallet refactor.

## Decisions

### D1 — Status-filtered uniqueness (Issue 1)

**Choice:** Narrow both app check and DB unique constraint to live statuses only.

- `_provider_ref_taken`: filter `status__in=[PENDING, COMPLETED]`.
- Unique constraint condition: existing recharge/provider/non-empty ref filters **plus** `status__in=['pending','completed']`.
- On reject: keep `external_ref` as-is for audit (do not tombstone).

**Alternatives considered:**

| Option | Why not preferred |
|--------|-------------------|
| Tombstone `external_ref` on reject (`…#rejected:{id}`) | Messier audit display; needs backfill for already-failed rows to unlock reuse |
| App-only filter without DB change | Races still hit IntegrityError; failed rows still block at DB |
| Delete failed rows | Violates production history rule |

**Status mapping:** Product “rejected” = model `failed`. Treat `cancelled` as non-blocking (same as failed) if any rows exist.

### D2 — Keep `customer_withdraw`; fix aggregation (Issue 2)

**Choice:** Do not change approve-withdraw ledger posting. Fix `period_totals` / dashboard:

- `expense` → sum completed debits where `type__in=EXPENSE_TYPES`.
- Add `customer_withdrawals` (period) → sum completed `customer_withdraw`.
- Optionally expose period admin `withdrawal` separately if useful; not required for the reported bug.
- Lifetime fields `total_expenses` / `total_customer_withdrawals` already diverge correctly — leave them.

**Alternatives considered:**

| Option | Why not preferred |
|--------|-------------------|
| New type `customer_withdrawal` | Duplicate of existing `customer_withdraw` |
| Relabel docs only (“expense” = cash out) | Leaves finance-misleading semantics |
| Rewrite historical rows from expense→withdraw | Code does not post expense today; rewrite unnecessary and unsafe |

**RCA note:** If operators observed `total_expenses` rising on withdraw approve, that would contradict current code; audit SQL must verify. The confirmed code bug is period dashboard aggregation/labeling.

### D3 — Production audit before schema change

**Choice:** Mandatory read-only report (management command or documented SQL) covering:

- Duplicate `(method, external_ref)` among `pending`+`completed` recharges (must be empty before migration).
- Counts of failed recharges that share refs with later completed ones (informational).
- Counts of Admin Wallet `customer_withdraw` vs expense-type rows in recent periods.
- Spot-check that withdraw-approve rows are not typed as expense.

No automatic rewrite of approved history. Optional failed-row cleanup is out of scope unless separately approved.

### D4 — Deploy order

1. Ship app-level `_provider_ref_taken` filter (or same release as constraint).
2. Apply constrained unique migration after live-duplicate audit passes.
3. Ship dashboard aggregation fix + docs in same release window as preferred (independent of Issue 1).

If app allows reuse while old constraint remains, create still fails with mapped `DuplicateProviderRefError` until migration lands — acceptable brief window; prefer same deploy.

### D5 — API compatibility for dashboard

**Choice:** Keep field names `today_expense` / `month_expense` but **change meaning** to expense-types only (**BREAKING** semantic). Add additive fields e.g. `today_customer_withdrawals` / `month_customer_withdrawals` so clients can show custody outflows separately.

Document in frontend Admin Wallet docs. Do not silently keep inflated expense numbers under the old name.

## Risks / Trade-offs

- [Concurrent create after many failed same-ref rows] → Mitigation: DB unique still enforces at most one live pending/completed per ref; app check + IntegrityError mapping retained.
- [Clients relying on inflated `today_expense` as cash-out] → Mitigation: additive withdrawal period fields + doc callout; coordinate with Admin Panel.
- [Constraint migration fails if unexpected live duplicates] → Mitigation: pre-migration audit gate; abort if any pending/completed duplicates found.
- [Misdiagnosis if production used wrong type historically] → Mitigation: audit counts by type; if wrong types found, plan a separate approved reconcile — not this change’s auto-migration.
- [Treating `cancelled` as free] → Mitigation: document; if product later needs cancelled to block, tighten filter.

## Migration Plan

1. **Audit (read-only)** on production replica/DB: run duplicate and type-count queries; store report in change notes / ops ticket.
2. **Code:** status-aware `_provider_ref_taken`; `period_totals` + dashboard fields; tests.
3. **Schema:** `RemoveConstraint` + `AddConstraint` for `wallet_txn_unique_provider_recharge_ref` with status filter (Django `UniqueConstraint` condition). No data UPDATE of approved rows.
4. **Docs:** wallet funding + admin wallet frontend/backend notes.
5. **Rollback:** revert app code; re-apply previous constraint condition if needed. Failed reused refs created after fix remain as data (do not mass-delete on rollback).

## Open Questions

- Confirm Admin Panel owners accept **BREAKING** semantic change for `today_expense` / `month_expense` (vs new field names only). Default in this design: keep names, fix meaning, add withdrawal period fields.
- Whether period admin `withdrawal` (platform cash-out) should appear on dashboard separately in this change or a follow-up.
- Whether any production rows incorrectly used expense types for customer withdraws (audit must answer before any optional reconcile proposal).
