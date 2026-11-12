# Tasks

## 1. Digest query and email service

- [x] 1.1 Add `delivery_zones` service module that queries active `CustomerSubscription` rows whose customer has null `delivery_sub_location`, ordered by `created_at`, and builds row dicts with name, phone, subscription time (Asia/Dhaka), and email (or N/A) — verify with unit tests covering include/exclude cases (active+null, active+assigned, cancelled)
- [x] 1.2 Implement admin digest email composer/sender reusing `resolve_funding_admin_emails()`, with plain + HTML table for non-empty runs and a short empty-run summary, skipping send when dry-run — verify with tests that assert recipient resolution, required columns, empty-run send, and dry-run no-send (mail outbox)
- [x] 1.3 Add a run/result helper (counts, slot label, `as_log_dict()`) that orchestrates query → email and isolates send failures into structured logs — verify the helper return shape in unit tests

## 2. Management command

- [x] 2.1 Create `delivery_zones/management/commands/` package (with `__init__.py` files) and `send_unassigned_delivery_digest` command supporting `--dry-run` and optional `--slot evening|night` — verify `manage.py send_unassigned_delivery_digest --dry-run` exits 0 and prints/logs candidate count without mailing
- [x] 2.2 Add command-level tests for success path (candidates present → email), empty path (empty summary email), and dry-run — verify Django test outbox expectations

## 3. Managed cron scripts

- [x] 3.1 Add `scripts/cron/run_unassigned_delivery_digest.sh` sourcing `_cron_env.sh`, with flock, `PYTHON_BIN` log line, and append to `logs/cron-unassigned-delivery-digest.log` — verify script is executable-ready (LF, shebang) and invokes the management command with absolute Python (match wallet wrapper pattern)
- [x] 3.2 Update `scripts/cron/install_managed_cron.sh` to chmod the new wrapper and register UTC jobs `0 12 * * *` and `0 16 * * *` inside the managed block with Asia/Dhaka comments, without removing auto-deliver/wallet jobs — verify installer echo/summary mentions the new schedules and the block lists six jobs
- [x] 3.3 Smoke-check installer block text (static assertion or shell dry inspection in test/docs) that both digest UTC lines are present and `CRON_TZ` remains absent — verify against `managed-cron-runtime` schedule list

## 4. Docs and integration check

- [x] 4.1 Document the digest command, schedules (18:00/22:00 Asia/Dhaka ↔ UTC), dry-run usage, and log path in `delivery_zones/docs/backend/` (zone-based delivery or a short dedicated ops note) — verify the doc names the command and both BD times
- [x] 4.2 Run the focused test module(s) for this change and confirm green — verify `python manage.py test` for the new digest tests passes
