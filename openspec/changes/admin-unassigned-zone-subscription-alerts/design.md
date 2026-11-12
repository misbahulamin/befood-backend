# Design

## Context

See proposal.md for motivation. Today:

- Operational assignment lives on `CustomerProfile.delivery_sub_location` (zone/location are derived). Subscription create does not require it.
- Admin directory already supports `has_active_subscription=true&has_delivery_sub_location=false`, but nothing proactively emails ops.
- Production scheduling uses managed Ubuntu cron (UTC host, Asia/Dhaka business times, no Celery beat). Wallet threshold digest is the closest pattern: management command → wrapper → installer → admin HTML/plain email via `resolve_funding_admin_emails()`.
- Project `TIME_ZONE` is already `Asia/Dhaka`.

## Goals / Non-Goals

**Goals:**

- Reuse existing admin recipient resolution, SMTP, and managed-cron conventions.
- Keep the digest query authoritative and cheap: active subscription + null sub-location.
- Make production scheduling automatic on next deploy via installer only.
- Keep the command operable locally with `--dry-run` and structured log output.

**Non-Goals:**

- Auto-assigning zones/sub-locations.
- Push notifications or in-app admin inbox UI.
- Alerting on inactive hierarchy (sub/location/zone status inactive) beyond null assignment.
- Changing subscription create validation to require zone assignment.
- New HTTP API endpoints or frontend work.
- Celery / Redis worker introduction.

## Decisions

### 1. Unassigned predicate = `delivery_sub_location IS NULL`

- **Choice:** Treat missing `CustomerProfile.delivery_sub_location` as the only inclusion rule for “not assigned.”
- **Why:** Matches assignment service truth (`resolve_operational_sub_location`) and admin customer filters (`has_delivery_sub_location=false`). Mirrored `delivery_location` alone is Bridge leftover and not operational.
- **Alternatives considered:** Also flag inactive hierarchy; deferred to keep noise low and match the user’s “assign hoy nai” wording.

### 2. Active subscription only

- **Choice:** `CustomerSubscription.status = active` (unique active per customer).
- **Why:** Matches dashboard/`get_active_subscription` product language. Cancelled rows are out even if `cancel_effective_on` is still in the future.
- **Alternatives considered:** Include cancelled-but-still-serving; rejected to avoid ops chasing churned customers for zone assignment.

### 3. Subscription time column = `created_at` (Asia/Dhaka)

- **Choice:** Show `CustomerSubscription.created_at` rendered in Asia/Dhaka RFC-style local timestamp in the email.
- **Why:** User asked for subscription time; `created_at` is when subscribe happened. `started_on` is a business date, less useful for “when did this land on us.”
- **Alternatives considered:** `started_on` only; rejected as less precise for ops triage.

### 4. Service placement under `delivery_zones` + shared email helpers

- **Choice:** Put query/run orchestration in `delivery_zones/services/unassigned_digest.py` (or similar) and a new `delivery_zones/management/commands/send_unassigned_delivery_digest.py`. Compose email similarly to `notifications/services/wallet_threshold_notifications.notify_admins_low_balance_summary` (inline plain + HTML table). Recipients via `wallet.services.funding_notifications.resolve_funding_admin_emails`.
- **Why:** Assignment domain owns the predicate; admin digest UX already proven in notifications/wallet; no new recipient registry.
- **Alternatives considered:** Put everything in `notifications/` only; rejected because candidate query is delivery-ops domain. Introduce a new settings-based recipient list; rejected as inconsistent with other admin digests.

### 5. Empty runs still email

- **Choice:** Always send a short empty summary on non-dry-run when candidates = 0.
- **Why:** Spec requires ops confirmation the cron fired; mirrors low-balance summary intent.
- **Alternatives considered:** Skip empty emails; rejected by product request for reliability signal.

### 6. Cron slots and wrapper CLI

- **Choice:** Wrapper `scripts/cron/run_unassigned_delivery_digest.sh` with optional slot arg `evening|night` for log clarity; both slots run the same command (full current unassigned set, not a time-window delta). UTC installer lines:
  - `0 12 * * *` → 18:00 Asia/Dhaka
  - `0 16 * * *` → 22:00 Asia/Dhaka
- **Why:** User asked for 6PM and 10PM BD; host cron is UTC; listing the full backlog each run is safer than “since last run” windows if a job is missed.
- **Alternatives considered:** Incremental “new since last digest” only; rejected (missed run would permanently hide customers). Celery beat; rejected (not in production architecture).

### 7. Command flags

- **Choice:** `--dry-run` (no send), optional `--slot evening|night` for logging context only.
- **Why:** Matches wallet/auto-deliver operability without inventing persistence.
- **Alternatives considered:** Persist last-sent ids for de-dupe; unnecessary because assignment removes the customer from the next list naturally.

### 8. No deploy YAML change

- **Choice:** Only extend `install_managed_cron.sh` + new wrapper; existing deploy hook already installs managed cron when the script exists.
- **Why:** Required by `managed-cron-install` / runtime specs.

## Risks / Trade-offs

- [Admin inbox noise twice daily, including empty runs] → Keep subject clear (`[BeFood] Unassigned delivery subscribers (N)` / empty variant); accept noise as reliability signal.
- [SMTP failure fails the cron] → Log and non-zero exit; same as other admin emails; ops see wrapper log.
- [Large unassigned backlog makes a huge email] → Unlikely early; if it grows, paginate/truncate with “+N more” in a follow-up change. Document soft expectation that list stays ops-sized.
- [Recipient set includes all verified ADMIN + superusers] → Same blast radius as wallet funding/support digests; no separate allowlist in v1.
- [Timezone confusion on host] → Keep UTC crontab fields + Asia/Dhaka comments; never set `CRON_TZ`.

## Migration Plan

1. Ship service + management command + tests.
2. Add wrapper + update `install_managed_cron.sh`.
3. Deploy; existing deploy step re-runs installer and replaces managed block with six UTC jobs.
4. Smoke: `manage.py send_unassigned_delivery_digest --dry-run`, then one live run in staging/prod off-schedule if needed.
5. Rollback: remove digest lines from installer and redeploy (or manually edit crontab managed block); code can remain inert without cron.

## Open Questions

None deferrable — product times, empty-run behavior, columns, and assignment predicate are fixed in specs.
