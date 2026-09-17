## Why

Pending withdraw reserves spendable balance at submit. That can push `Wallet.balance` below `meal_stop_threshold`, after which cron (or another path) sets `meal_service_blocked_low_balance=true`. Admin reject correctly releases the reservation and restores balance, but unlike recharge approve it never calls `maybe_resume_after_wallet_credit`, so customers stay meal-blocked even when post-reject balance is again `>= meal_stop_threshold`.

## What Changes

- After a successful **withdraw reject** credit (reservation release), evaluate meal-stop resume with the same shared helper used by recharge approve / `credit_wallet`.
- Clear `meal_service_blocked_low_balance` / `meal_service_blocked_at` when post-reject spendable balance meets the live threshold; keep the block when still below.
- Surface `meal_service_restored` on the admin **reject** success response for withdraw (same meaning as approve), so admin UI can toast optionally.
- Reuse existing post-resume cutoff-skip behavior via `resume_meal_service_after_balance_recovery` (no new skip rules).
- No dedicated “meal restored” customer push/email; no migration.

## Capabilities

### New Capabilities

- `meal-service-resume-on-withdraw-reject`: Withdraw reject restores reservation then resumes low-balance meal-stop when balance meets threshold; admin reject response reports `meal_service_restored`.

### Modified Capabilities

- `low-balance-recharge-cutoff-skip`: Treat successful withdraw-reject resume as another shared resume entry point that MUST apply the same past-cutoff skip rules.
- `meal-service-resume-on-recharge-approval`: Clarify that admin **reject** responses MAY return `meal_service_restored=true` for withdraw reject (today docs/tests treat reject as always `false`).

## Impact

- **Code:** `wallet/services/funding.py` (`reject_withdraw`); `wallet/api/web_views.py` reject action + OpenAPI; optional serializer context wiring already used on approve.
- **Tests:** Extend `wallet/tests/test_meal_service_resume_on_approve.py` (or sibling) for withdraw-reject restore / keep-block / API field.
- **Docs:** `wallet/docs/frontend/manual-wallet-funding.md` and related backend funding notes.
- **Unchanged:** Withdraw approve (still no restore); recharge reject (no credit); auto delivery skip-on-block; meal-stop threshold cron.
