## Context

Production observation (Asia/Dhaka): lunch auto-delivery at **15:00** marks eligible `OrderDelivery` rows `delivered` and debits wallets. Customers who fall below `OrderWalletSettings.meal_stop_threshold` (e.g. `100.00`) remain with `CustomerProfile.meal_service_blocked_low_balance=false` until the **20:00** host cron runs `check_wallet_balance_thresholds`. Kitchen Today `final_cooking_count` excludes blocked customers via that flag only (not live `Wallet.balance`), so dinner cook counts stay high through the kitchen prep window (~16:00+) and drop when the evening cron finally blocks (observed 25 → 23). Dinner auto-delivery at **23:00** already skips blocked customers, so kitchen can over-cook.

Important correction vs ops assumptions: **15:00 does not create orders/slots**. Slot rows come from subscribe / `ensure_subscription_deliveries`. Auto-deliver only transitions `scheduled` → `delivered` and charges. There is **no Celery** for this path; automation is Ubuntu crontab via `scripts/cron/install_managed_cron.sh`.

Stakeholders: kitchen ops (accurate cook counts), finance/wallet (meal-stop reserve), customers (timely meal pause + notifications).

## Goals / Non-Goals

**Goals:**

- Close the 15:00 → 20:00 gap: after a **successful** meal-payment debit, evaluate spendable balance vs `meal_stop_threshold` and apply the same stop semantics as the wallet-threshold cron (`balance < threshold` → block).
- Keep Kitchen Today / auto-deliver behavior flag-based so existing exclusion logic continues to work once the flag flips immediately.
- Preserve 08:00 / 20:00 cron for reminders, resume, admin summary, and non-meal-debit balance drift.
- No schema migration; reuse `apply_meal_service_block`, `spendable_balance`, `get_order_wallet_settings`.

**Non-Goals:**

- Changing `meal_stop_threshold` meaning, meal-off cutoffs, or Kitchen API response shape.
- Switching kitchen demand to live `balance < threshold` (Meal Close already has a broader low-balance view; aligning formulas is a separate product decision).
- Removing the twice-daily wallet cron or adding a mandatory 15:05/23:05 cron as the primary fix.
- Blocking on every wallet debit type (withdraw, admin adjust, etc.) — only **successful meal-delivery payment** in this change (cron still covers other paths).
- Backfilling historical over-cook incidents.

## Decisions

### D1 — Post-charge evaluation in the meal-payment success path (Option A), keep cron (hybrid)

**Choice:** Call a shared helper (e.g. `evaluate_meal_stop_after_debit(customer)`) immediately after a successful `charge_delivered_meal` debit commits (or inside the same atomic block after wallet balance is updated), for both auto-delivery and operator mark-delivered.

**Why over Option B only (extra cron after deliver):** A 15:05 cron still leaves a window where Kitchen Today over-counts during dinner prep. Post-charge evaluation updates the flag before ops refresh kitchen counts. Cron alone also misses mid-day operator mark-delivered charges.

**Why keep cron:** Resume, daily reminder, admin summary, and customers who drop below threshold without a meal debit still need the 08:00/20:00 job.

**Alternatives considered:** Hook all `debit_wallet` call sites (too broad; withdraw already has meal-stop floor elsewhere). Live-balance kitchen exclusion without flag (diverges from auto-deliver eligibility which uses the flag; risk of inconsistent skip/cook rules).

### D2 — Extract stop-only evaluate helper; do not run full cron per customer inside deliver

**Choice:** Extract stop/resume comparison for a single customer from `wallet_balance_thresholds.py` (reuse `apply_meal_service_block` + `spendable_balance` + threshold settings). Post-charge path applies **stop** when `balance < meal_stop_threshold`. Do not send full cron reminder/admin-summary side effects from deliver batches.

**Notifications:** On newly blocked, reuse the same customer meal-stop notify path the cron uses for newly blocked customers (push/email policy consistent with cron). Failures in notify MUST NOT roll back a successful charge.

**Idempotency:** If already blocked, `apply_meal_service_block` is a no-op; repeated mark-delivered / idempotent charge MUST NOT re-block or spam incorrectly beyond existing cron notify rules (prefer notify only when newly blocked on this path).

### D3 — Placement: after successful charge in `charge_delivered_meal` (or thin wrapper)

**Choice:** Prefer invoking evaluation once from `charge_delivered_meal` after a real debit (and after idempotent attach that already charged historically — skip re-evaluate if no balance change this call). That covers auto-deliver and operator mark-delivered without duplicating hooks.

**Transaction:** Prefer evaluating after wallet balance is updated in the same atomic success path so the read sees the post-debit balance. If notify must be outside the atomic block, use `transaction.on_commit` for notifications only; block flag write stays with the successful charge transaction when practical.

**Alternatives:** End-of-batch in `run_auto_delivery` only (misses operator mark-delivered). Separate 15:05 cron only (rejected as primary).

### D4 — Kitchen formula unchanged

**Choice:** Keep `final_cooking_count` exclusion on `meal_service_blocked_low_balance`. Immediate flag update is enough for counts to drop on the next Kitchen Today GET. No cache layer to invalidate.

### D5 — No DB migration

Existing fields and settings are sufficient.

## Risks / Trade-offs

- **[Risk] Notify latency / failure after charge** → Mitigation: block flag is source of truth; notify best-effort on_commit; charge remains committed.
- **[Risk] Auto-deliver batch slows if notify is sync per customer** → Mitigation: keep notify lightweight; consider batching later; evaluation itself is O(1) per charged customer.
- **[Risk] Strict `<` threshold surprises at exact equality** → Mitigation: keep existing cron rule (`balance < meal_stop` stop; `>=` resume); do not change inequality in this fix.
- **[Risk] Meal Close still shows live-balance “low” while flag false for non-charge drops** → Mitigation: accepted until evening cron; document; optional follow-up for live-balance kitchen alignment.
- **[Trade-off] Hybrid (post-charge + cron)** vs single mechanism → Slight duplication of stop logic, reduced by shared helper; better coverage than either alone.

## Migration Plan

1. Deploy code + tests; no migrate step.
2. Confirm managed cron still installs 08:00/20:00 wallet check and 15:00/23:00 auto-deliver unchanged.
3. Smoke: charge a test customer below threshold via lunch auto-deliver or mark-delivered → flag true before 20:00; Kitchen Today dinner count excludes them.
4. Rollback: revert deploy; behavior returns to cron-only blocking (no schema rollback needed).

## Open Questions

- Should post-charge path also clear the block if somehow balance is already `>= threshold` after debit? (Normally debit only lowers balance; resume remains credit/cron responsibility — default **no resume on debit path**.)
- Product follow-up: align Meal Close live-balance list vs kitchen flag-only exclusion in a later change?
