# Spec Delta

## Purpose

Provide a scheduled, operable backend job that builds and sends the unassigned-delivery admin digest twice daily in Asia/Dhaka without requiring manual operator runs in production.

## ADDED Requirements

### Requirement: Twice-daily unassigned delivery digest cron

The system SHALL provide a Django management command that builds the unassigned-delivery admin digest and sends it to verified admins. Managed production cron MUST schedule that command at approximately 18:00 and 22:00 Asia/Dhaka via the repository-owned managed cron installer and a dedicated wrapper script.

#### Scenario: Evening and night schedules installed

- **WHEN** `scripts/cron/install_managed_cron.sh` is run on a production host
- **THEN** the managed crontab block includes unassigned-delivery digest jobs for 18:00 and 22:00 Asia/Dhaka in addition to existing auto-delivery and wallet-threshold jobs

#### Scenario: Command dry-run

- **WHEN** an operator runs the unassigned-delivery digest management command with `--dry-run`
- **THEN** the command reports how many qualifying customers would be emailed without sending notifications

### Requirement: Wrapper logs and isolates failures

A dedicated wrapper script under `scripts/cron/` SHALL invoke the digest management command with absolute venv Python, append stdout/stderr to a project log file, and use non-blocking flock when available. Failures composing or sending the digest MUST be visible in that log and MUST exit non-zero for operator diagnosis.

#### Scenario: Wrapper failure visible in logs

- **WHEN** the digest management command exits non-zero
- **THEN** stderr/stdout for that run is captured in the cron log for operator diagnosis

#### Scenario: Dry-run does not send email

- **WHEN** the wrapper or operator invokes the command with `--dry-run`
- **THEN** no admin digest email is sent for that invocation
