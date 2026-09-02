## Context

BeFood already has a singleton `OrderWalletSettings` with `min_wallet_balance_to_order` (default `500.00` BDT). Verified admins manage it via `GET/PATCH /api/v1/web/orders/order-wallet-settings/`; Admin Frontend Settings uses the same contract. Subscribe eligibility calls `check_subscribe_wallet` → `check_wallet_min_balance` (inclusive `balance >= min`). Meal delivery charges only at mark-delivered via `debit_wallet`; auto-delivery cron retries `scheduled` slots and does **not** pause subscriptions on low balance.

Notifications: FCM via `send_to_tokens` (meal-delivered pattern). Email: branded `EmailMultiAlternatives` + `email_branding`; admin recipients via `resolve_funding_admin_emails()` (verified ADMIN + superusers).

Managed cron: `scripts/cron/install_managed_cron.sh` already installs lunch/dinner auto-delivery inside `# BEGIN/END BEFOOD-MANAGED`. Deploy YAML already invokes this script — **must not be edited**.

Stakeholders: verified admins (configure thresholds + receive ops report), customers (reminder / meal stop), kitchen (fewer unpaid auto-delivery retries).

## Goals / Non-Goals

**Goals:**

- Three ordered wallet thresholds on the existing settings singleton.
- Twice-daily cron (08:00 / 20:00 Asia/Dhaka) evaluating verified customers with active meal service.
- Low-balance reminder (push + email) and meal-stop (block auto meal processing + notify).
- Admin summary email with structured user rows after each run.
- Admin Frontend Settings UI for all three thresholds with conflict validation.
- Production-ready managed cron install without CI/CD YAML changes.
- Preserve manual admin mark-delivery and customer meal-off flows; reuse wallet ledger and notification/email infra.

**Non-Goals:**

- Per-package or per-customer custom thresholds.
- Adding a `paused` subscription status enum (deferred earlier; out of scope).
- Changing subscribe debit behavior or meal charge price rules.
- Editing `.github/workflows/deploy.yml`.
- Mass-skipping historical/future delivery rows on stop (prefer eligibility gate + auto-resume).
- Customer-facing settings write APIs for thresholds.

## Decisions

### D1 — Extend `OrderWalletSettings`, do not add a second settings model

- **Choice:** Add `low_balance_reminder_threshold` (default `300.00`) and `meal_stop_threshold` (default `200.00`) on `OrderWalletSettings`. Keep `min_wallet_balance_to_order` as the subscription minimum (field name unchanged for API compatibility; help text already subscribe-oriented).
- **Why:** Same singleton + admin GET/PATCH + Admin Settings page pattern; no new route surface for MVP.
- **Alternatives:** New `WalletThresholdSettings` model → duplicate admin plumbing; env vars → not admin-editable.

### D2 — Strict ordering validation at serializer/service layer

- **Choice:** On PATCH, require  
  `min_wallet_balance_to_order > low_balance_reminder_threshold > meal_stop_threshold ≥ 0`,  
  each with ≤ 2 decimal places. Reject partial updates that would violate order when merged with current stored values.
- **Why:** Matches product rule; prevents nonsense configs like reminder above subscribe gate.
- **Alternatives:** Soft warnings only → ops can still save broken configs.

### D3 — Meal-stop as customer-level block flag, not subscription `paused`

- **Choice:** Persist on `CustomerProfile` (or equivalent customer-owned row):
  - `meal_service_blocked_low_balance` (bool, default false)
  - `meal_service_blocked_at` (nullable datetime)
  - `last_low_balance_reminder_on` (nullable date, Asia/Dhaka business date) for reminder idempotency
- **Why:** Avoids widening `CustomerSubscription.Status`; unique-active-subscription constraint stays intact; one block covers the customer’s meal service.
- **Behavior:**
  - **Apply stop:** set flag when spendable `Wallet.balance < meal_stop_threshold`.
  - **Auto-delivery:** `eligible_delivery_queryset` / live eligibility MUST exclude blocked customers so cron does not keep failing charges.
  - **Manual admin mark-delivery:** MUST remain allowed (ops override).
  - **Customer meal-off / meal-on:** unchanged.
  - **Auto-resume:** when balance ≥ `meal_stop_threshold` (on cron evaluation and/or after successful wallet credit), clear the block flag; future `scheduled` slots become eligible again without mass rewrites.
- **Alternatives:** `status=paused` → migration + API contract churn; system-skip all future slots → painful resume and audit noise.

### D4 — Cron orchestration service + management command

- **Choice:**
  - Service: `orders.services.wallet_balance_thresholds.run_wallet_threshold_check(*, as_of=None, dry_run=False) -> RunResult`
  - Command: `manage.py check_wallet_balance_thresholds [--dry-run]`
  - Wrapper: `scripts/cron/run_wallet_threshold_check.sh` (venv + flock + log under `logs/`)
  - Installer: extend `MANAGED_BLOCK` with `0 8 * * *` and `0 20 * * *` Asia/Dhaka lines
- **Why:** Mirrors auto-meal-delivery pattern; testable; deploy reinstalls crontab idempotently.
- **Audience query:** verified customers (`CustomerProfile` email-verified + CUSTOMER group conventions already used elsewhere) who have an **active** subscription and/or currently blocked flag (so resume still runs). Frozen wallets still evaluated for stop/reminder messaging as product safety (optional note in tasks: treat frozen like low for stop).

### D5 — Case priority and messaging

- **Choice:** Per customer each run:
  1. If `balance < meal_stop_threshold` → ensure blocked; send meal-stop push+email if newly blocked **or** once per business day while still blocked (prefer: notify on transition to blocked only; admin report always includes).
  2. Else if blocked and `balance ≥ meal_stop_threshold` → clear block (resume); no reminder required unless also `< reminder`.
  3. Else if `balance < low_balance_reminder_threshold` → send reminder push+email at most once per business day (`last_low_balance_reminder_on`).
- **Why:** Meal-stop is stricter; avoids double-spam; daily cadence matches twice-daily cron without flooding.
- **Message content (English templates):** reminder warns that service stops below meal-stop amount; stop message says recharge to resume.

### D6 — Reuse FCM + branded email; admin report like funding notifications

- **Choice:** Customer push via `send_to_tokens` with `data.type` of `wallet_low_balance` / `wallet_meal_stop`. Customer email via branded HTML templates under `templates/emails/`. Admin summary via `resolve_funding_admin_emails()` (or shared rename-safe helper), HTML **table** (Excel-like columns: Name, Phone, Package, Current Balance, Address, Status) plus optional plain-text fallback. Failures are best-effort: log and continue; never abort the whole batch on one user.
- **Why:** Existing ops already receive funding emails from the same recipient set.

### D7 — Frontend stays on Admin Settings; API additive

- **Choice:** Extend `OrderWalletSettings` serializer response/request with the two new fields. Admin Settings form adds two inputs + client validation mirroring server order. Customer wallet GET may expose the new thresholds read-only for UX (additive, non-breaking).
- **Why:** No new admin page; same verified-admin permission.

### D8 — Documentation and tests in-repo

- **Choice:** Backend doc `orders/docs/backend/wallet-balance-thresholds.md` (and short frontend note if FE lives in sibling repo). Tests for settings ordering, cron case matrix, eligibility exclusion, resume-on-credit/cron, and admin email recipient path (mocked mail).

## Risks / Trade-offs

- **[Risk] Manual deliveries while blocked still charge wallet** → **Mitigation:** Document as intentional ops override; charge path unchanged.
- **[Risk] Reminder spam if cron retries / clock skew** → **Mitigation:** Persist `last_low_balance_reminder_on` business date; meal-stop notify primarily on transition.
- **[Risk] Default thresholds violate order if migrate with weird existing min** → **Mitigation:** Data migration sets defaults `300`/`200`; if existing `min_wallet_balance_to_order` ≤ 300, clamp reminder/stop below min or leave admin to fix with validation on next PATCH.
- **[Risk] OpenSpec allowed edit root is backend-only** → **Mitigation:** Spec/tasks describe FE work in `F:\befood\befood-frontend`; implement FE in that repo during apply (or sibling checkout).
- **[Risk] Blocked users accumulate forever-scheduled slots** → **Mitigation:** Acceptable; auto-resume re-enables eligibility; kitchen demand already uses live filters—confirm meal-demand queries also exclude blocked if needed.
- **[Trade-off] Strict `>` ordering** forbids equal thresholds → Clearer bands; admins must leave headroom.

## Migration Plan

1. Add model fields + migration with defaults `300.00` / `200.00`; backfill existing singleton row.
2. Ship API/serializer validation + service helpers.
3. Ship meal-stop flag + eligibility exclusion + resume hooks.
4. Ship notification/email templates + cron command/wrapper.
5. Extend `install_managed_cron.sh`; deploy pulls and reinstalls crontab (no YAML change).
6. Update Admin Frontend Settings form.
7. Rollback: remove cron lines via installer revert / empty job; leave thresholds unused; clear block flags via management command if needed. Feature can be no-op if cron wrapper disabled.

## Open Questions

- Should customer wallet GET expose reminder/stop thresholds immediately, or admin-only until customer UX is ready? **Default:** expose read-only on wallet GET (additive).
- Exact copy for Bengali vs English emails — **Default:** English templates first (match meal-delivery / funding tone); BN optional follow-up.
- Include customers without active subscription but balance below reminder? **Default:** only active subscribers + currently blocked (for resume).
