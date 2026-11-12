# Spec Delta

## ADDED Requirements

### Requirement: Managed installer registers unassigned-delivery digest jobs

The repository-owned managed cron installer at `scripts/cron/install_managed_cron.sh` SHALL register unassigned-delivery digest jobs at approximately 18:00 and 22:00 Asia/Dhaka inside the existing `# BEGIN BEFOOD-MANAGED` / `# END BEFOOD-MANAGED` block, without removing existing auto-delivery or wallet-threshold jobs. The installer MUST remain idempotent and MUST NOT require edits to `.github/workflows/deploy.yml`.

#### Scenario: Installer adds evening and night digest checks

- **WHEN** an operator or deploy hook runs `scripts/cron/install_managed_cron.sh`
- **THEN** the managed crontab contains unassigned-delivery digest wrapper invocations for 18:00 and 22:00 Asia/Dhaka alongside existing auto-delivery and wallet-threshold entries

#### Scenario: Reinstall does not duplicate digest jobs

- **WHEN** the installer is run twice after a schedule or path change
- **THEN** exactly one managed block remains and unassigned-delivery digest job lines are not duplicated

### Requirement: Unassigned-delivery digest wrapper uses venv and logging

A dedicated wrapper script under `scripts/cron/` SHALL activate the project virtualenv, run the unassigned-delivery digest management command, and append output to a log file under the project logs directory. Non-zero exits MUST be visible in that log.

#### Scenario: Digest wrapper failure visible in logs

- **WHEN** the unassigned-delivery digest management command exits non-zero
- **THEN** stderr/stdout for that run is captured in the cron log for operator diagnosis
