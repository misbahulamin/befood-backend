## 1. Audit baseline (no code changes yet)

- [x] 1.1 Re-read `.github/workflows/deploy.yml` sync section and confirm it still uses `git pull --ff-only` (failure mode to fix)
- [x] 1.2 Confirm production layout assumptions in docs/scripts: `PROJECT_DIR=/home/ubuntu/befood-backend`, sibling `VENV=/home/ubuntu/venv`
- [x] 1.3 Audit `scripts/cron/_cron_env.sh`, `run_auto_deliver.sh`, `run_wallet_threshold_check.sh`, `install_managed_cron.sh` against specs (absolute Python, flock/logs, schedules, markers)
- [x] 1.4 Confirm `.gitattributes` contains `*.sh text eol=lf` and note any gaps

## 2. Deterministic production deploy sync

- [x] 2.1 Update `.github/workflows/deploy.yml` to replace `git pull --ff-only origin main` with `git fetch origin main` + checkout `main` + log `git status --short` + `git reset --hard origin/main`
- [x] 2.2 Do **not** add stash/pop restore of tracked files; do **not** enable broad `git clean -fd` unless a documented exclude list is proven necessary
- [x] 2.3 Keep subsequent steps intact: venv activate, pip, `manage.py check/migrate/collectstatic`, `install_managed_cron.sh`, nginx test, supervisor restart, health checks
- [x] 2.4 Optionally assert `HEAD` equals `origin/main` after reset (fail deploy if mismatch)

## 3. Cron / LF gap fixes (only if audit finds issues)

- [x] 3.1 If any `scripts/cron/*.sh` contains CR bytes, convert to LF-only and keep content otherwise unchanged
- [x] 3.2 If wrappers still call bare `python` or miss sibling `../venv`, fix via `_cron_env.sh` / wrappers to use absolute `PYTHON_BIN`
- [x] 3.3 If installer schedules/markers/idempotency regress, restore Asia/Dhaka jobs and `# BEGIN/END BEFOOD-MANAGED` without duplicates; ensure `chmod +x` on wrappers
- [x] 3.4 If audit finds no gaps, record “no script changes required” and leave scripts untouched

## 4. Docs (ops verification only)

- [x] 4.1 Update or add a short note in existing cron docs (`orders/docs/backend/auto-meal-delivery.md` and/or `wallet-balance-thresholds.md`) describing deploy hard-reset behavior and post-deploy verification commands
- [x] 4.2 Ensure docs do not change schedules or Django command names

## 5. Local verification

- [x] 5.1 Run `bash -n` on all `scripts/cron/*.sh`
- [x] 5.2 Confirm zero CR bytes under `scripts/cron/`
- [x] 5.3 Confirm `.gitattributes` still enforces `*.sh text eol=lf`
- [x] 5.4 Diff-review `deploy.yml` for accidental removal of cron install or service restart steps

## 6. Production verification (after merge/deploy)

- [ ] 6.1 Confirm GitHub Actions deploy succeeds end-to-end
- [ ] 6.2 On EC2: `cd /home/ubuntu/befood-backend && git status` is clean and `git rev-parse HEAD` matches `origin/main`
- [ ] 6.3 Confirm `crontab -l` contains one BEFOOD-MANAGED block with the four expected jobs
- [ ] 6.4 Manually run wallet and auto-deliver wrappers; confirm logs under `logs/` and non-zero exit on forced failure paths if tested
- [ ] 6.5 Confirm `.env` still present and app health checks still pass
