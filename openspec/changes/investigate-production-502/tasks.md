## 1. Repo architecture freeze (read-only code scan)

- [ ] 1.1 Document exact call chain from `scripts/cron/run_auto_deliver.sh` → `_cron_env.sh` → `manage.py auto_deliver_meals` → `run_auto_delivery` → `mark_delivery_and_notify` → charge / notify with file paths and function names
- [ ] 1.2 Document eligibility queryset, PK materialization (`values_list`), per-slot reload, and that 15:00/23:00 jobs do not create delivery slots
- [ ] 1.3 Inventory `@transaction.atomic` / `select_for_update` usage on the mark + wallet path (`mark_delivery`, `charge_delivered_meal`, `debit_wallet`, meal-stop)
- [ ] 1.4 Inventory synchronous side effects per delivered slot (Onahar, referral commission, inbox, FCM `send_to_tokens`) and note they run outside money rollback for notify
- [ ] 1.5 Document dual lock protection: shell `flock` wrapper lock + Python `auto_delivery_process_lock`, plus domain idempotency
- [ ] 1.6 Confirm production DB engine is PostgreSQL from `core/settings/prod.py` and note deploy process model: Nginx → `app.sock` → Supervisor `guni:*`

## 2. Cron configuration verification (repo + host read-only)

- [ ] 2.1 Record managed UTC crontab lines from `install_managed_cron.sh` with Asia/Dhaka equivalents (08:00 / 15:00 / 20:00 / 23:00)
- [ ] 2.2 On host (read-only): `crontab -l` and `sudo crontab -l`; confirm managed block and check for duplicate `run_auto_deliver` lines outside the block
- [ ] 2.3 Confirm wrapper is foreground, logs to `logs/cron-auto-deliver-{lunch|dinner}.log`, and lock files under `tmp/locks/`
- [ ] 2.4 Note behavior when previous run still holds lock (`lock busy` exit) and whether `flock` binary exists on the host

## 3. Nginx / Gunicorn upstream discovery (host read-only)

- [ ] 3.1 Locate Nginx site for `api.befood.com.bd`; record `proxy_pass`, timeouts, and upstream socket/port
- [ ] 3.2 Confirm expected unix socket `/home/ubuntu/befood-backend/app.sock` exists and permissions/ownership
- [ ] 3.3 Locate Supervisor `guni:*` program conf; record Gunicorn workers, worker class, timeout, graceful timeout, max requests, preload, bind, log paths
- [ ] 3.4 Build Nginx 502 error-class cheat sheet from live `error.log` samples (connect refused, missing socket, premature close, reset, timed out)

## 4. Incident log correlation (host read-only)

- [ ] 4.1 For next or last lunch window (`14:55–15:10` Asia/Dhaka / `08:55–09:10` UTC), collect cron start/finish, candidate counts, and errors from `cron-auto-deliver-lunch.log`
- [ ] 4.2 For dinner window (`22:55–23:10` Asia/Dhaka / `16:55–17:10` UTC), collect the same from `cron-auto-deliver-dinner.log`
- [ ] 4.3 Correlate Nginx error.log upstream lines in the same windows
- [ ] 4.4 Correlate Supervisor/Gunicorn logs for TIMEOUT, worker exit/boot, SIGKILL, Traceback in the same windows
- [ ] 4.5 Search kernel/journal for OOM killer hits on gunicorn/python in the same windows and nearby
- [ ] 4.6 Capture host snapshot metrics: `free`, swap, load, `df -h`, `df -i` (and note if historical metrics are unavailable)
- [ ] 4.7 If Postgres access allows, run read-only `pg_stat_activity` / `pg_locks` checks around a window; otherwise mark DB contention inconclusive
- [ ] 4.8 Fill design Appendix C timeline table and write verdict: confirmed / refuted / coincidence / inconclusive

## 5. Safe command pack + investigation report

- [ ] 5.1 Publish a single operator-facing checklist (or `orders/docs/backend/` / ops note) containing the read-only commands from design Appendix B, with `# READ-ONLY` and explicit forbid list for mutations
- [ ] 5.2 Write root-cause investigation report summarizing architecture facts, host evidence (redacted), timeline, and verdict; do not include secrets
- [ ] 5.3 If verdict is confirmed or points to a specific layer, open a follow-up OpenSpec change for remediations only; do not apply production fixes under this investigation change
- [ ] 5.4 If inconclusive, document missing log retention / next capture plan for the following 15:00 and 23:00 runs

## 6. Guardrails

- [ ] 6.1 Verify no Phase 1 task recommends or requires `supervisorctl restart`, `systemctl restart`, `kill`, migrate, package install, or crontab rewrite
- [ ] 6.2 Verify report does not treat code-review risks (e.g. sync FCM) as root cause without runtime correlation
