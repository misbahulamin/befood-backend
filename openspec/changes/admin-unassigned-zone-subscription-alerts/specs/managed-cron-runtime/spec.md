# Spec Delta

## MODIFIED Requirements

### Requirement: Managed installer emits UTC schedules without CRON_TZ

`install_managed_cron.sh` MUST remain the sole crontab installer invoked by deploy, MUST NOT require deploy YAML changes, MUST NOT emit `CRON_TZ`, MUST `chmod +x` wrapper scripts, and MUST install absolute-path jobs inside `# BEGIN BEFOOD-MANAGED` … `# END BEFOOD-MANAGED` with comments stating host cron timezone is UTC and business timezone is Asia/Dhaka, using these UTC schedules:

- `0 9 * * *` → `run_auto_deliver.sh lunch` (15:00 Asia/Dhaka)
- `0 17 * * *` → `run_auto_deliver.sh dinner` (23:00 Asia/Dhaka)
- `0 2 * * *` → `run_wallet_threshold_check.sh` (08:00 Asia/Dhaka)
- `0 14 * * *` → `run_wallet_threshold_check.sh` (20:00 Asia/Dhaka)
- `0 12 * * *` → `run_unassigned_delivery_digest.sh` evening/18:00 slot (18:00 Asia/Dhaka)
- `0 16 * * *` → `run_unassigned_delivery_digest.sh` night/22:00 slot (22:00 Asia/Dhaka)

The installer MUST replace any previous managed block (including old `CRON_TZ` and Bangladesh-hour schedules) and MUST remain idempotent (running twice MUST NOT duplicate jobs).

#### Scenario: Idempotent install yields UTC jobs only

- **WHEN** `bash scripts/cron/install_managed_cron.sh` runs on a host whose system timezone is UTC
- **THEN** `crontab -l` MUST contain exactly one managed block with the six UTC schedules above, MUST include host/business timezone comments, MUST NOT contain `CRON_TZ`, and MUST NOT retain prior Asia/Dhaka hour fields (`15`, `23`, `8`, `20`, `18`, `22`) inside the managed block as local-hour cron fields

#### Scenario: Re-run replaces old CRON_TZ block

- **WHEN** the existing crontab still has a managed block with `CRON_TZ=Asia/Dhaka` and Bangladesh-hour schedules
- **THEN** re-running the installer MUST replace that block with the UTC schedules and MUST leave no duplicate auto-deliver, wallet-threshold, or unassigned-delivery digest lines outside the markers

#### Scenario: Digest schedules map to Bangladesh evening and night

- **WHEN** the managed installer has been applied on a UTC host
- **THEN** the managed block includes `0 12 * * *` and `0 16 * * *` invocations of the unassigned-delivery digest wrapper corresponding to 18:00 and 22:00 Asia/Dhaka

## ADDED Requirements

### Requirement: Unassigned-delivery digest wrapper follows managed runtime rules

The unassigned-delivery digest wrapper MUST resolve absolute venv Python using the same discovery order as other managed wrappers, MUST `cd` to the project root containing `manage.py`, MUST append output under `logs/`, and MUST use non-blocking flock under `tmp/locks/` when `flock` is available. Successful runs MUST log a line containing `PYTHON_BIN=` with the absolute interpreter path.

#### Scenario: Digest wrapper uses absolute interpreter

- **WHEN** `bash scripts/cron/run_unassigned_delivery_digest.sh` runs successfully with a valid venv
- **THEN** the process MUST invoke the digest management command with absolute `PYTHON_BIN`, append to its project log file, and MUST NOT call bare `python`
