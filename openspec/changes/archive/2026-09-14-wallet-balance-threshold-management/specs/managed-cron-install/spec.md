## ADDED Requirements

### Requirement: Managed installer registers wallet-threshold jobs

The repository-owned managed cron installer at `scripts/cron/install_managed_cron.sh` SHALL register wallet balance threshold check jobs at approximately 08:00 and 20:00 Asia/Dhaka inside the existing `# BEGIN BEFOOD-MANAGED` / `# END BEFOOD-MANAGED` block, without removing existing auto-delivery lunch/dinner jobs. The installer MUST remain idempotent and MUST NOT require edits to `.github/workflows/deploy.yml`.

#### Scenario: Installer adds morning and evening wallet checks

- **WHEN** an operator or deploy hook runs `scripts/cron/install_managed_cron.sh`
- **THEN** the managed crontab contains wallet-threshold wrapper invocations for 08:00 and 20:00 Asia/Dhaka alongside existing auto-delivery entries

#### Scenario: Reinstall does not duplicate wallet jobs

- **WHEN** the installer is run twice after a schedule or path change
- **THEN** exactly one managed block remains and wallet-threshold job lines are not duplicated

### Requirement: Wallet-threshold wrapper uses venv and logging

A dedicated wrapper script under `scripts/cron/` SHALL activate the project virtualenv, run the wallet-threshold management command, and append output to a log file under the project logs directory. Non-zero exits MUST be visible in that log.

#### Scenario: Wrapper failure visible in logs

- **WHEN** the wallet-threshold management command exits non-zero
- **THEN** stderr/stdout for that run is captured in the cron log for operator diagnosis

### Requirement: Deploy YAML remains unchanged

Implementation of these cron jobs MUST NOT require edits to existing GitHub Actions deploy workflow files. Presence of the updated `install_managed_cron.sh` is sufficient for the existing deploy step to install jobs.

#### Scenario: Deploy hook installs without workflow change

- **WHEN** this change is deployed with the updated installer present
- **THEN** the existing deploy step that invokes the installer can refresh crontab without a workflow file change in the same PR
