## 1. Production audit (read-only, gate)

- [x] 1.1 Document and run SQL/report for duplicate `(method, external_ref)` among provider recharges with `status IN (pending, completed)` — must be empty before constraint migration
- [x] 1.2 Report counts of failed provider recharges and any same-ref pairs (failed + later completed/pending) for ops visibility
- [x] 1.3 Report Admin Wallet completed row counts by type for recent periods, especially `customer_withdraw` vs `EXPENSE_TYPES`, and confirm withdraw approvals are not typed as expense
- [x] 1.4 Record audit results in the change notes / ops ticket; stop if live pending/completed duplicates exist

## 2. Provider transaction id reuse (Issue 1)

- [x] 2.1 Update `_provider_ref_taken` in `wallet/services/funding.py` to only match `status__in=[PENDING, COMPLETED]`
- [x] 2.2 Update `WalletTransaction` Meta unique constraint `wallet_txn_unique_provider_recharge_ref` condition to include live statuses only
- [x] 2.3 Add Django migration that replaces the constraint without rewriting approved or failed row data
- [x] 2.4 Confirm `reject_recharge` still sets `failed`, leaves `external_ref` intact, and does not move balances

## 3. Admin Wallet expense vs withdraw (Issue 2)

- [x] 3.1 Confirm `debit_from_customer_withdraw` / approve path still posts `customer_withdraw` and updates `total_customer_withdrawals` (no code change unless audit finds a bug)
- [x] 3.2 Change `period_totals` in `admin_wallet/services/queries.py` so `expense` sums only `EXPENSE_TYPES`
- [x] 3.3 Add period customer-withdrawal totals and expose them on dashboard payload (today/month)
- [x] 3.4 Update Admin Wallet API serializers/OpenAPI if dashboard response fields are declared there

## 4. Tests

- [x] 4.1 Test: pending same `transaction_id` → duplicate blocked
- [x] 4.2 Test: completed/approved same `transaction_id` → duplicate blocked
- [x] 4.3 Test: reject to `failed` then recreate same `transaction_id` → allowed
- [x] 4.4 Test: withdraw approve → customer balance reduced, Admin balance reduced, ledger type `customer_withdraw`, `total_expenses` unchanged
- [x] 4.5 Test: dashboard `today_expense` excludes `customer_withdraw` and includes operational expense; period customer-withdrawal field includes withdraw amount

## 5. Documentation

- [x] 5.1 Update wallet funding frontend/backend docs for provider `transaction_id` reuse after reject
- [x] 5.2 Update Admin Wallet frontend/backend docs for expense vs customer-withdrawal dashboard semantics (**BREAKING** meaning of expense fields)
- [x] 5.3 Note deploy order: audit → app+constraint → dashboard fields; rollback notes from design.md

## 6. Verification

- [x] 6.1 Run targeted wallet funding and admin wallet test suites
- [x] 6.2 Smoke: reject recharge → reuse same trx id; approve withdraw → dashboard expense unchanged, withdrawal period total increases
