## Why

Production wallet accounting has two consistency bugs that hurt customers and mislead admin finance views: (1) rejected provider recharge `transaction_id` values remain permanently unique, so customers cannot resubmit a real payment after a failed review; (2) Admin Wallet dashboard period “expense” aggregates treat all completed debits as business expense, so approved customer withdrawals inflate expense cards even though the ledger already posts them as custody `customer_withdraw`. Both must be fixed with minimal, production-safe changes that never rewrite approved history.

## What Changes

- Narrow provider recharge duplicate detection so only `pending` and `completed` rows block the same `(method, external_ref)` / `transaction_id`; `failed` (rejected) and non-blocking statuses allow reuse.
- Align the database unique constraint `wallet_txn_unique_provider_recharge_ref` with that status filter (no deletion/rewrite of existing approved or rejected rows beyond what the constraint migration requires).
- Keep Admin Wallet withdraw approve posting as `customer_withdraw` (not expense types); do **not** invent a new ledger type unless audit proves one is missing.
- Fix Admin Wallet dashboard / `period_totals` so `today_expense` / `month_expense` sum only `EXPENSE_TYPES` (business costs), not custody outflows like `customer_withdraw` or admin `withdrawal`.
- Add explicit period fields for customer withdrawals (and document any API field semantics change).
- Run a read-only production data audit report before applying schema/behavior changes; historical approved recharge/withdraw ledger rows MUST NOT be auto-rewritten.
- Add regression tests for reject→reuse recharge and withdraw-approve ledger/dashboard classification.
- Update backend/frontend docs for provider-ref uniqueness and dashboard expense meaning.

## Capabilities

### New Capabilities

- `wallet-provider-ref-reuse`: Rules for when a provider payment `transaction_id` (`external_ref`) may be reused on a new recharge request after prior outcomes (pending/completed block; failed/rejected allow).

### Modified Capabilities

- `wallet-funding`: Provider recharge uniqueness and reject behavior must match the reuse rules above without changing approve/reject notification or custody sync flows beyond uniqueness.
- `admin-wallet-funding-custody`: Clarify that approved customer withdraw MUST debit Admin Wallet as `customer_withdraw` custody release and MUST NOT increment lifetime `total_expenses` or be classified as business expense.
- `admin-wallet-admin-api`: Dashboard period expense aggregates MUST exclude non-expense debit types; expose separate customer-withdrawal period totals.
- `admin-wallet-frontend-docs`: Document corrected expense vs customer-withdrawal dashboard semantics and recharge `transaction_id` reuse after reject.

## Impact

- **Code:** `wallet/services/funding.py` (`_provider_ref_taken`, reject/create paths), `wallet/models.py` + migration for unique constraint condition, `wallet/tests/*`, `admin_wallet/services/queries.py` (`period_totals` / `dashboard_payload`), admin wallet API serializers/docs, possibly frontend docs under `wallet/docs` and `admin_wallet/docs`.
- **APIs:** Recharge create duplicate error becomes status-aware; Admin Wallet dashboard expense numbers may decrease for periods that included customer withdrawals (**BREAKING** semantic change for clients that treated `today_expense` / `month_expense` as “all cash out”).
- **Data:** Existing failed recharge rows keep their `external_ref` for audit; approved history untouched. Constraint migration must be preceded by a duplicate audit among live statuses.
- **Out of scope:** Full wallet refactor, new wallet architecture, automatic rewrite of historical admin ledger types/counters, notification system redesign.
