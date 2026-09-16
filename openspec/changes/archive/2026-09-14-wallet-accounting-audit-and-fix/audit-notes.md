# Audit notes — wallet-accounting-audit-and-fix

## Tooling

```bash
python manage.py audit_wallet_accounting
```

Reports:

1. Live `(method, external_ref)` duplicates among provider recharges with `status IN (pending, completed)` — **must be empty** before migration `0004_live_status_provider_recharge_ref_unique`.
2. Failed provider recharge counts; failed refs that also have a live row; failed-only reuse candidates.
3. Admin Wallet completed row counts by type; confirms linked customer withdraws use `customer_withdraw` (not expense types).

Exit code `1` if live duplicates exist (abort constraint migration).

## Local / CI run

Run the command against the target DB before production migrate. Record stdout in the deploy ticket.

**This workspace (dev sqlite) run (2026-09-08):**

```
=== 1. Live provider-ref duplicates ===
OK: no pending/completed provider recharge duplicates.
=== 2. Failed provider recharges ===
Failed provider recharges with non-empty external_ref: 0
Failed refs that also have a live pending/completed row: 0
Failed-only provider refs (reuse candidates after fix): 0
=== 3. Admin Wallet completed types ===
  inventory_purchase: 3
  customer_funding: 2
  manual_deposit: 1
Completed customer_withdraw rows: 0
Completed EXPENSE_TYPES rows (sum): 3
Admin rows linked to customer withdraw txns: customer_withdraw=0, other_types=0
OK: linked customer withdraws use type=customer_withdraw (not expense).
=== Summary ===
PASS: safe to proceed with live-status uniqueness migration (this DB).
```

Migration `wallet.0004_live_status_provider_recharge_ref_unique` applied successfully on this DB.

**Production must re-run** `python manage.py audit_wallet_accounting` on the production DB/replica before migrate.

## Deploy order

1. Run `audit_wallet_accounting` on production (or replica) — gate.
2. Deploy app code (`_provider_ref_taken` + dashboard `period_totals`) **with** migration in the same release when possible.
3. Apply `wallet.0004_live_status_provider_recharge_ref_unique` (includes live-duplicate RunPython guard).
4. Update Admin Panel to use expense vs customer-withdrawal period fields.

## Rollback

- Revert app code; re-apply previous unique constraint condition if needed.
- Do **not** mass-delete failed recharges or rewrite approved history on rollback.
- Dashboard field meaning: if rolling back aggregation fix, clients that already switched to expense-only must tolerate old “all debit” expense again.

## Code confirmation (Issue 2 ledger path)

`debit_from_customer_withdraw` posts `AdminWalletTransaction.Type.CUSTOMER_WITHDRAW` and lifetime counters update `total_customer_withdrawals`, not `total_expenses`. No ledger-type change required; dashboard aggregation only.
