## Context

Meal-stop already works in production:

- Cron / threshold checker uses `spendable_balance(customer)` which reads **`Wallet.balance`** (there is no `available_balance` / `spendable_balance` column on Wallet).
- When `balance < meal_stop_threshold`, cron sets `CustomerProfile.meal_service_blocked_low_balance`.
- Auto meal delivery skips blocked customers; that path must not change.
- `maybe_resume_after_wallet_credit(customer: CustomerProfile | None) -> bool` already exists: takes a **CustomerProfile**, compares `spendable_balance` to live `meal_stop_threshold`, calls `clear_meal_service_block`, returns **`True`/`False`**, never raises.
- `credit_wallet` schedules that helper on `on_commit`; `approve_recharge` credits inline and **does not** call it today.
- Meal-stop customer notify today runs mainly when **newly** blocked; reminder band uses `last_low_balance_reminder_on` (once per business day). Product now wants a **push on every cron run** while still below meal-stop, without that daily gate.

Stakeholders: verified admins approving recharges; customers under meal-stop; ops cron; kitchen/delivery unchanged.

## Goals / Non-Goals

**Goals:**

- Wire `approve_recharge` → `restored = maybe_resume_after_wallet_credit(profile)` in the same atomic as the credit; map `restored` to API `meal_service_restored` without re-querying flags for that boolean.
- Keep resume balance/threshold math identical to cron/`credit_wallet` via the shared helper (`Wallet.balance` through `spendable_balance`).
- No migration; no “meal service restored” customer notification; keep existing recharge-approved notifications.
- On each threshold cron evaluation with `spendable_balance < meal_stop_threshold`, send Low Wallet Balance Alert push (repeat allowed same day); apply meal-stop block as today (separate step).
- Do **not** use `last_low_balance_reminder_on` for this meal-stop-band warning push.

**Non-Goals:**

- Changing auto meal delivery eligibility beyond the existing block flag.
- Frontend threshold calculation or a new approve UX (optional admin toast only).
- Refactoring `approve_recharge` through `credit_wallet`.
- Changing withdraw approve / reject / pending submit.
- New customer push/email for “meal service restored” after approve.
- Removing or redesigning the separate once-per-day reminder at `low_balance_reminder_threshold` (out of scope unless product consolidates later).
- Spamming meal-stop **email** on every cron run (push is the required channel for the new repeat warning; keep email on newly-blocked transition unless product expands).

## Decisions

### D1 — Helper boolean is the API source of truth

- **Choice:** `restored = maybe_resume_after_wallet_credit(profile)` where `profile` is the wallet’s `CustomerProfile`. Use that bool for `meal_service_restored`.
- **Why:** Helper already returns whether a block was cleared (`clear_meal_service_block` → bool). Avoids a second profile query in `funding.py` solely for the response field.
- **Verify before implement:** Signature is `(CustomerProfile | None) -> bool`; balance path is `spendable_balance` → `Wallet.balance`; same as cron. If that remains true at apply time, production wiring is safe.
- **Alternatives considered:** Re-read `meal_service_blocked_low_balance` after helper (extra query); inline clear in funding (duplicates math).

### D2 — Same balance source as cron (no duplicate calculation)

- **Choice:** Never invent a parallel “available” formula in funding. Only call the shared helper / `spendable_balance`.
- **Why:** Wallet model exposes `balance` only; cron and resume already share `spendable_balance`.
- **Verified:** No `available_balance` field on `Wallet`.

### D3 — Same DB transaction as approval credit (not `on_commit`)

- **Choice:** Sync call inside `approve_recharge`’s `@transaction.atomic` after balance write.
- **Why:** Credit + unblock commit together; approve response can include the helper bool without relying on `on_commit` ordering. Leave `credit_wallet`’s on_commit path unchanged.

### D4 — No restore notification; no migration

- **Choice:** Recharge-approved push/email remain; do not add “Your meal service restored”. No new DB fields.
- **Why:** Product-confirmed; schema already has block fields.

### D5 — Admin `meal_service_restored` additive; frontend minimal

- **Choice:** Serializer/OpenAPI boolean on approve `200`. Customer apps unchanged. Admin optional: if `meal_service_restored == true` show “Meal service restored”.
- **Why:** Backend owns the decision; clients ignore unknown fields safely.

### D6 — Meal-stop-band cron push every run (no daily idempotency)

- **Choice:** In `run_wallet_threshold_check`, when `balance < stop_threshold` (non-dry-run), after ensuring block state, **always** send the Low Wallet Balance Alert push for that customer on that run—whether newly blocked or already blocked. Do not consult `last_low_balance_reminder_on` for this push.
- **Copy (push):**
  - Title: `Low Wallet Balance Alert`
  - Body: `Hi {customer_full_name}, your current wallet balance is low. Please recharge your wallet soon to continue receiving your meals. If your balance remains low, your meal service will be paused.`
- **Why:** Product wants morning + night warnings while still under meal-stop (max ~2/day with current schedule).
- **Alternatives considered:** Keep notify-only-on-transition (fails product); reuse reminder helper + daily flag (explicitly forbidden for this warning).
- **Email:** Keep meal-stop email on **newly blocked** only to limit inbox noise (push carries the every-run warning). Document if product later wants email every run too.
- **Reminder band:** Unchanged (`balance < reminder_threshold` and not meal-stopped path priority as today, once per business day).

### D7 — Block vs notify remain separate steps

- **Choice:** Detect low balance → send warning push → apply/ensure `meal_service_blocked_low_balance=true` (order may be notify-after-block as long as both happen on the same evaluation when below threshold). Delivery pause still driven only by the flag.
- **Why:** Matches product flow; cron skip logic untouched.

## Risks / Trade-offs

- **[Risk] Helper returns False after swallowed exception → credit without unblock** → **Mitigation:** Log already exists; cron resume remains backup; prefer not to invent a second clear path.
- **[Risk] Twice-daily push feels spammy** → **Mitigation:** Explicit product rule; capped by cron schedule (~2/day).
- **[Risk] Overlap with existing `wallet_meal_stop` / reminder copy** → **Mitigation:** Use the new title/body for the every-run meal-stop-band push; keep data `type` documented (prefer stable `wallet_meal_stop` or a documented alias—pick one in implement and update OpenAPI/docs).
- **[Risk] Serializer/API clients assume fixed approve schema** → **Mitigation:** Additive boolean only.
- **[Trade-off] Not unifying approve into `credit_wallet`** → Smaller, safer diff.

## Migration Plan

1. Code-only deploy (no schema migration).
2. Pending recharges gain resume-on-approve immediately.
3. Next cron runs send every-run meal-stop-band pushes while under threshold.
4. Optional admin UI toast for `meal_service_restored`.
5. Rollback: revert funding hook + cron notify frequency; cron still resumes/blocks as before.

## Open Questions

- None blocking. Optional later: every-run meal-stop **email**; consolidate reminder-band vs meal-stop-band messaging.
