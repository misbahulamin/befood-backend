## ADDED Requirements

### Requirement: Twice-daily wallet threshold cron

The system SHALL provide a Django management command that evaluates wallet balances against configured reminder and meal-stop thresholds. Managed production cron MUST schedule that command at approximately 08:00 and 20:00 in `Asia/Dhaka` via the repository-owned managed cron installer and a dedicated wrapper script.

#### Scenario: Morning and evening schedules installed

- **WHEN** `scripts/cron/install_managed_cron.sh` is run on a production host
- **THEN** the managed crontab block includes wallet-threshold check jobs for 08:00 and 20:00 Asia/Dhaka in addition to existing auto-delivery jobs

#### Scenario: Command dry-run

- **WHEN** an operator runs the wallet-threshold management command with `--dry-run`
- **THEN** the command reports which customers would be reminded, stopped, or resumed without sending notifications or changing block state

### Requirement: Cron evaluates active verified subscribers

Each cron execution SHALL load configured thresholds, evaluate verified customers with an active meal subscription (and customers currently blocked for resume), apply meal-stop then reminder priority, and invoke the admin low-balance summary for the run.

#### Scenario: Combined case handling in one run

- **WHEN** the cron runs and one customer is below meal-stop and another is only below reminder
- **THEN** the first is meal-stopped (and notified per meal-stop rules), the second receives a reminder (subject to daily idempotency), and both appear in the admin summary as applicable

### Requirement: Batch isolation and logging

Per-customer failures during threshold evaluation MUST be isolated: one customer’s error MUST NOT prevent processing of remaining customers. The wrapper SHALL append stdout/stderr to a project log file.

#### Scenario: One customer notification failure

- **WHEN** email sending fails for one qualifying customer during a cron run
- **THEN** the run continues for other customers and the failure is visible in logs
