## 1. Line endings hygiene

- [x] 1.1 Confirm root `.gitattributes` contains `*.sh text eol=lf` (add/update if missing)
- [x] 1.2 Ensure every file under `scripts/cron/` ending in `.sh` is LF-only (zero `\r` bytes) and renormalize in Git if needed

## 2. Shared cron environment helper

- [x] 2.1 Add `scripts/cron/_cron_env.sh` that resolves `PROJECT_DIR`, discovers `VENV_PATH` / absolute `PYTHON_BIN` (override → sibling `../venv` → `PROJECT_DIR/venv` → `PROJECT_DIR/.venv`), fails loudly if missing, and sets unset `DJANGO_ENV`/`DJANGO_SETTINGS_MODULE` defaults for prod
- [x] 2.2 Keep the helper LF-only and sourceable via absolute path from wrappers

## 3. Harden wrappers

- [x] 3.1 Update `scripts/cron/run_wallet_threshold_check.sh` to source `_cron_env.sh`, run `"${PYTHON_BIN}" manage.py check_wallet_balance_thresholds`, preserve flock + `logs/cron-wallet-threshold-check.log`
- [x] 3.2 Update `scripts/cron/run_auto_deliver.sh` to source `_cron_env.sh`, run `"${PYTHON_BIN}" manage.py auto_deliver_meals --meal-period ...`, preserve flock + meal-period logs and usage validation
- [x] 3.3 Confirm `install_managed_cron.sh` still installs the same managed schedules/markers, chmods wrappers executable, and does not edit deploy YAML or hardcode wrong venv paths

## 4. Docs

- [x] 4.1 Update `orders/docs/backend/auto-meal-delivery.md` with production layout (`/home/ubuntu/befood-backend` + sibling `/home/ubuntu/venv`), absolute-Python note, and verification commands
- [x] 4.2 Update `orders/docs/backend/wallet-balance-thresholds.md` with the same production runtime / verification notes

## 5. Verification

- [x] 5.1 Run `bash -n` on all `scripts/cron/*.sh` (including `_cron_env.sh`)
- [x] 5.2 Confirm no CR via byte check / `grep` for `$'\r'` under `scripts/cron/`
- [x] 5.3 Document (and run if a matching local layout exists) manual smoke: wrappers + expected log paths; note remaining production-only risks (crontab permissions, wrong sibling venv)
