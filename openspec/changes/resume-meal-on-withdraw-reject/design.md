## Context

Today:

- Withdraw submit reserves spendable balance (`request_withdraw` debits recharge bucket immediately; txn stays `pending`).
- If post-reserve balance falls below `meal_stop_threshold`, cron / other paths set `CustomerProfile.meal_service_blocked_low_balance=true`.
- `approve_recharge` already calls `maybe_resume_after_wallet_credit` in the same atomic as the credit and exposes `meal_service_restored` on admin approve `200`.
- `reject_withdraw` credits the reserved amount back via `_apply_credit` but does **not** evaluate meal-stop resume, so the block flag can stay `true` after balance recovery.
- Shared helper `maybe_resume_after_wallet_credit` → `resume_meal_service_after_balance_recovery` already clears the block when `spendable_balance >= meal_stop_threshold` and applies past-cutoff system skips.

Stakeholders: verified admins rejecting withdraws; customers under meal-stop; kitchen/auto-delivery consumers of the block flag.

## Goals / Non-Goals

**Goals:**

- Wire `reject_withdraw` → `maybe_resume_after_wallet_credit(wallet.customer)` after reservation release, same atomic as the credit.
- Attach transient `meal_service_restored` for admin reject API (withdraw path), mirroring approve.
- Keep resume math identical to recharge approve / cron (`Wallet.balance` via `spendable_balance`, live `meal_stop_threshold`).
- Document frontend: reject `200` may include `meal_service_restored=true` for withdraw.

**Non-Goals:**

- Changing withdraw approve (still no restore).
- Changing recharge reject (no balance credit).
- New customer “meal restored” notification.
- Schema / migration.
- Changing when meal-stop is **applied** after withdraw submit (cron / other existing paths remain).
- Frontend threshold calculation.

## Decisions

### D1 — Reuse the same helper as recharge approve

- **Choice:** Call `maybe_resume_after_wallet_credit(wallet.customer)` inside `reject_withdraw` after wallet save / ledger snapshot, assign `locked_txn.meal_service_restored = <bool>`.
- **Why:** One resume implementation; includes cutoff-skip via `resume_meal_service_after_balance_recovery`; never raises.
- **Alternatives considered:** Inline `clear_meal_service_block` only (skips cutoff rules); `on_commit` only (harder to return bool on reject response).

### D2 — Same atomic as reservation release (not only `on_commit`)

- **Choice:** Sync call inside `@transaction.atomic` on `reject_withdraw`, matching `approve_recharge`.
- **Why:** Credit + unblock commit together; reject response can report the helper bool without relying on commit hooks.

### D3 — Admin reject response reuses `meal_service_restored`

- **Choice:** Pass `meal_service_restored` through reject action context for withdraw (default `false` for recharge reject). Update OpenAPI description; docs already have the field on the funding serializer.
- **Why:** Same contract as approve; additive; clients that ignore unknown/false fields stay safe.
- **Alternatives considered:** Silent flag clear with no API field (harder for admin ops toast / debugging).

### D4 — Insufficient restore keeps block

- **Choice:** If post-reject balance is still `< meal_stop_threshold`, helper returns `false` and flags stay blocked.
- **Why:** Identical to insufficient recharge approve.

### D5 — No new notification

- **Choice:** Do not add push/email for meal restore on withdraw reject.
- **Why:** Matches recharge-approve product decision; balance restore is admin-driven rejection, not a customer funding success event.

## Risks / Trade-offs

- **[Risk] Helper swallows exceptions → credit without unblock** → **Mitigation:** Existing helper logging; next wallet-threshold cron still resumes when balance stays above threshold.
- **[Risk] Docs/tests assumed reject always has `meal_service_restored=false`** → **Mitigation:** Update frontend manual-funding doc + meal resume tests; keep recharge-reject false.
- **[Trade-off] Reject of recharge still never resumes** → Correct: no credit occurs.

## Migration Plan

1. Code-only deploy (no DB migration).
2. Existing pending withdraws gain resume-on-reject immediately after deploy.
3. Optional admin toast when reject returns `meal_service_restored=true`.
4. Rollback: revert `reject_withdraw` hook + reject view context; cron resume remains backup for already-credited wallets.

## Open Questions

- None blocking.
