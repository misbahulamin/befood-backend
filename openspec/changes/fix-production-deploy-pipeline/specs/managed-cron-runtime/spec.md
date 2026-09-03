## ADDED Requirements

### Requirement: Cron wrappers resolve absolute venv Python

Managed cron wrapper scripts MUST resolve an absolute Python executable from a virtualenv and MUST NOT rely on cron PATH alone to find `python`. Discovery MUST prefer (in order): environment override `BEFOOD_VENV` or `VENV_PATH` when it contains `bin/python`; sibling directory `dirname(PROJECT_DIR)/venv`; `PROJECT_DIR/venv`; `PROJECT_DIR/.venv`. If no executable Python is found, the wrapper MUST log a clear error and exit non-zero.

#### Scenario: Production sibling venv is used

- **WHEN** the project is at `/home/ubuntu/befood-backend` and Python exists at `/home/ubuntu/venv/bin/python`
- **THEN** `run_wallet_threshold_check.sh` and `run_auto_deliver.sh` MUST invoke that absolute interpreter to run `manage.py` without requiring `python` on PATH

#### Scenario: Missing venv fails loudly

- **WHEN** none of the discovery candidates contain an executable `bin/python`
- **THEN** the wrapper MUST write an error to its log (or stderr before logging is set up) and exit with a non-zero status instead of calling bare `python`

### Requirement: Wrappers preserve project root, flock, and logging

Each wrapper MUST `cd` to the resolved project root (directory containing `manage.py`), append run output to the existing log path under `logs/`, and use non-blocking flock on the existing lock file under `tmp/locks/` when `flock` is available. Management command names and flags MUST remain unchanged (`check_wallet_balance_thresholds`; `auto_deliver_meals --meal-period lunch|dinner`). Failures from the management command MUST appear in the wrapper log and MUST surface as a non-zero process exit status (subject to `set -e` / pipeline behavior already used by the wrappers).

#### Scenario: Wallet threshold wrapper keeps behavior

- **WHEN** `bash scripts/cron/run_wallet_threshold_check.sh` runs successfully with a valid venv
- **THEN** the process MUST append to `logs/cron-wallet-threshold-check.log` and run `manage.py check_wallet_balance_thresholds` from the project root

#### Scenario: Auto-deliver wrapper keeps meal period behavior

- **WHEN** `bash scripts/cron/run_auto_deliver.sh lunch` runs successfully with a valid venv
- **THEN** the process MUST append to `logs/cron-auto-deliver-lunch.log` and run `manage.py auto_deliver_meals --meal-period lunch`

### Requirement: Managed installer stays idempotent with fixed schedules

`install_managed_cron.sh` MUST idempotently replace the `# BEGIN BEFOOD-MANAGED` … `# END BEFOOD-MANAGED` block without duplicating entries, MUST keep `CRON_TZ=Asia/Dhaka`, MUST keep schedules `0 15 * * *` lunch auto-deliver, `0 23 * * *` dinner auto-deliver, and `0 8 * * *` / `0 20 * * *` wallet threshold checks, MUST point crontab entries at absolute wrapper paths under `PROJECT_DIR/scripts/cron/`, and MUST ensure those wrappers are marked executable. Deploy MUST continue to invoke this installer after code sync.

#### Scenario: Idempotent install without duplicate jobs

- **WHEN** `bash scripts/cron/install_managed_cron.sh` runs twice on the same host
- **THEN** `crontab -l` MUST contain exactly one managed block with the schedules above and MUST NOT duplicate those four job lines outside the markers
