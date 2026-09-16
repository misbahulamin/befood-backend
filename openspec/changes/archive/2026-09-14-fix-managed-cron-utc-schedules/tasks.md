## 1. Fix managed cron timezone handling

- [x] 1.1 Update `scripts/cron/install_managed_cron.sh`: remove `CRON_TZ=Asia/Dhaka` entirely from the managed block
- [x] 1.2 Install UTC schedules with absolute paths: `0 9` lunch, `0 17` dinner, `0 2` and `0 14` wallet threshold
- [x] 1.3 Add managed-block comments: `# Host cron timezone: UTC` and `# Business timezone: Asia/Dhaka`
- [x] 1.4 Keep idempotent marker replace (strip old block including prior `CRON_TZ` / BD hours; running twice must not duplicate jobs) and `chmod +x` on wrappers

## 2. Audit cron Python environment

- [x] 2.1 Audit `scripts/cron/_cron_env.sh` discovery order: `BEFOOD_VENV` → `VENV_PATH` → sibling `../venv` → `PROJECT_DIR/venv` → `PROJECT_DIR/.venv`; never fall back to bare `python`
- [x] 2.2 Confirm `run_auto_deliver.sh` / `run_wallet_threshold_check.sh` invoke only `"${PYTHON_BIN}" manage.py …` with unchanged command contracts
- [x] 2.3 Confirm success logs include `PYTHON_BIN=/absolute/path`; fail non-zero with clear error if no interpreter found
- [x] 2.4 Do not modify Django delivery services, `mark_delivery`, wallet charging, notifications, management commands, or `.github/workflows/deploy.yml`

## 3. Keep locking and logging

- [x] 3.1 Verify flock + `tmp/locks/` behavior remains for both wrappers
- [x] 3.2 Verify log paths remain: `logs/cron-wallet-threshold-check.log`, `logs/cron-auto-deliver-lunch.log`, `logs/cron-auto-deliver-dinner.log`

## 4. Fix documentation

- [x] 4.1 Update `orders/docs/backend/auto-meal-delivery.md`: EC2 UTC, crontab UTC, Asia/Dhaka business meaning, `CRON_TZ` intentionally unused, expected managed-block example
- [x] 4.2 Update `orders/docs/backend/wallet-balance-thresholds.md` with the same timezone/schedule guidance (08:00/20:00 BD → 02:00/14:00 UTC)

## 5. Validation

- [x] 5.1 Run `bash -n` on `install_managed_cron.sh`, `run_auto_deliver.sh`, and `run_wallet_threshold_check.sh`
- [x] 5.2 Run CRLF check (`grep` for `$'\r'` on `scripts/cron/*.sh`) and confirm no output
- [x] 5.3 Show `git diff --stat` and `git status`; ensure only required files (no `.env`, `logs/`, `tmp/locks/`, media/test noise) — ready for commit
