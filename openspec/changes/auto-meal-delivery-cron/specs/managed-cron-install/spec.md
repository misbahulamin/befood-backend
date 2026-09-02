## ADDED Requirements

### Requirement: Managed cron installer is repository-owned

The repository SHALL include a managed cron installer at `scripts/cron/install_managed_cron.sh` that production deploy can invoke without modifying `.github/workflows/deploy.yml`. The installer MUST be idempotent: re-running after `git pull` updates the managed crontab block to match the repo definition and MUST NOT duplicate job lines.

#### Scenario: Installer creates lunch and dinner auto-delivery jobs

- **WHEN** an operator (or deploy hook) runs `scripts/cron/install_managed_cron.sh` on a host with crontab access and a configured project/venv path
- **THEN** the user crontab contains managed entries that invoke lunch auto-delivery around 15:00 and dinner auto-delivery around 23:00 in Asia/Dhaka (or an equivalent CRON_TZ configuration)

#### Scenario: Second install replaces managed block without duplicates

- **WHEN** the installer is run twice after a schedule or command path change in the repo
- **THEN** exactly one managed block remains and job lines are not duplicated

### Requirement: Deploy YAML remains unchanged

Implementation of managed cron MUST NOT require edits to existing GitHub Actions deploy workflow files. Presence of `scripts/cron/install_managed_cron.sh` is sufficient for the existing deploy step to install jobs.

#### Scenario: Missing installer is not required for this change after ship

- **WHEN** this change is merged with the installer present
- **THEN** the existing deploy step that checks for that script path can install jobs without a workflow file change in the same PR

### Requirement: Cron wrappers use project venv and logging

Managed job wrappers SHALL activate the project virtualenv, run the Django management command for the intended meal period, and append output to a rotatable or dated log file under the project logs directory (or an agreed ops path).

#### Scenario: Wrapper failure is visible in logs

- **WHEN** the auto-delivery management command exits non-zero
- **THEN** stderr/stdout for that run is captured in the cron log so operators can diagnose wallet or pricing failures
