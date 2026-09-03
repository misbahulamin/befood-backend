## ADDED Requirements

### Requirement: Cron wrappers resolve absolute venv Python

Managed cron wrapper scripts MUST resolve an absolute Python executable from a virtualenv and MUST NEVER invoke bare `python` (including `python manage.py …`). Discovery MUST prefer this order:

1. `${BEFOOD_VENV}/bin/python` when `BEFOOD_VENV` is set
2. `${VENV_PATH}/bin/python` when `VENV_PATH` is set
3. `$(dirname "${PROJECT_DIR}")/venv/bin/python` (production sibling, e.g. `/home/ubuntu/venv/bin/python`)
4. `${PROJECT_DIR}/venv/bin/python`
5. `${PROJECT_DIR}/.venv/bin/python`

If no executable interpreter is found, the wrapper MUST log a clear error and exit non-zero. Successful runs MUST log a line containing `PYTHON_BIN=` with the absolute interpreter path.

#### Scenario: Production sibling venv is used

- **WHEN** the project is at `/home/ubuntu/befood-backend` and Python exists at `/home/ubuntu/venv/bin/python`
- **THEN** `run_wallet_threshold_check.sh` and `run_auto_deliver.sh` MUST invoke that absolute interpreter to run `manage.py` without requiring `python` on PATH

#### Scenario: Missing venv fails loudly

- **WHEN** none of the discovery candidates contain an executable `bin/python`
- **THEN** the wrapper MUST write an error to its log (or stderr before logging is set up) and exit with a non-zero status instead of calling bare `python`

#### Scenario: Log records interpreter path

- **WHEN** a wrapper starts a management-command invocation with a resolved interpreter
- **THEN** the wrapper log line MUST include `PYTHON_BIN=` followed by that absolute path

### Requirement: Wrappers preserve project root, flock, and logging

Each wrapper MUST `cd` to the resolved project root (directory containing `manage.py`), append run output to the existing log path under `logs/`, and use non-blocking flock on the existing lock file under `tmp/locks/` when `flock` is available. Locking and logging MUST NOT be removed. Management command names and flags MUST remain unchanged (`check_wallet_balance_thresholds`; `auto_deliver_meals --meal-period lunch|dinner`).

#### Scenario: Wallet threshold wrapper keeps behavior

- **WHEN** `bash scripts/cron/run_wallet_threshold_check.sh` runs successfully with a valid venv
- **THEN** the process MUST append to `logs/cron-wallet-threshold-check.log` and run `manage.py check_wallet_balance_thresholds` from the project root

#### Scenario: Auto-deliver wrapper keeps meal period behavior

- **WHEN** `bash scripts/cron/run_auto_deliver.sh lunch` runs successfully with a valid venv
- **THEN** the process MUST append to `logs/cron-auto-deliver-lunch.log` and run `manage.py auto_deliver_meals --meal-period lunch`

#### Scenario: Dinner auto-deliver log path preserved

- **WHEN** `bash scripts/cron/run_auto_deliver.sh dinner` runs successfully with a valid venv
- **THEN** the process MUST append to `logs/cron-auto-deliver-dinner.log`

### Requirement: Managed installer emits UTC schedules without CRON_TZ

`install_managed_cron.sh` MUST remain the sole crontab installer invoked by deploy, MUST NOT require deploy YAML changes, MUST NOT emit `CRON_TZ`, MUST `chmod +x` wrapper scripts, and MUST install absolute-path jobs inside `# BEGIN BEFOOD-MANAGED` … `# END BEFOOD-MANAGED` with comments stating host cron timezone is UTC and business timezone is Asia/Dhaka, using these UTC schedules:

- `0 9 * * *` → `run_auto_deliver.sh lunch` (15:00 Asia/Dhaka)
- `0 17 * * *` → `run_auto_deliver.sh dinner` (23:00 Asia/Dhaka)
- `0 2 * * *` → `run_wallet_threshold_check.sh` (08:00 Asia/Dhaka)
- `0 14 * * *` → `run_wallet_threshold_check.sh` (20:00 Asia/Dhaka)

The installer MUST replace any previous managed block (including old `CRON_TZ` and Bangladesh-hour schedules) and MUST remain idempotent (running twice MUST NOT duplicate jobs).

#### Scenario: Idempotent install yields UTC jobs only

- **WHEN** `bash scripts/cron/install_managed_cron.sh` runs on a host whose system timezone is UTC
- **THEN** `crontab -l` MUST contain exactly one managed block with the four UTC schedules above, MUST include host/business timezone comments, MUST NOT contain `CRON_TZ`, and MUST NOT retain prior Asia/Dhaka hour fields (`15`, `23`, `8`, `20`) inside the managed block

#### Scenario: Re-run replaces old CRON_TZ block

- **WHEN** the existing crontab still has a managed block with `CRON_TZ=Asia/Dhaka` and Bangladesh-hour schedules
- **THEN** re-running the installer MUST replace that block with the UTC schedules and MUST leave no duplicate auto-deliver or wallet-threshold lines outside the markers
