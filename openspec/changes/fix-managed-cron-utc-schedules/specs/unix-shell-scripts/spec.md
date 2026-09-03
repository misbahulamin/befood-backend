## ADDED Requirements

### Requirement: Cron shell scripts use LF and valid bash syntax

Shell scripts under `scripts/cron/` that are executed on Linux production MUST use Unix LF line endings (no CRLF) and MUST pass `bash -n` syntax checks so Ubuntu bash and cron can run them without `set: pipefail`-class failures.

#### Scenario: Installer and wrappers pass bash -n

- **WHEN** an operator runs `bash -n` on `install_managed_cron.sh`, `run_auto_deliver.sh`, and `run_wallet_threshold_check.sh`
- **THEN** each check MUST exit zero with no syntax errors

#### Scenario: No CRLF in managed cron scripts

- **WHEN** `grep -R $'\r' scripts/cron/*.sh` (or equivalent) is run after the change
- **THEN** the command MUST produce no output (no carriage-return bytes in those scripts)

### Requirement: Commit tree contains only required cron fix files

After implementation, the working tree prepared for commit MUST include only the cron installer/wrappers/env (if changed), the two backend docs, and this change’s planning artifacts as needed — and MUST NOT stage `.env`, `logs/`, `tmp/locks/`, or media/test artifacts.

#### Scenario: Status is commit-ready

- **WHEN** an operator runs `git status` and `git diff --stat` after the fix
- **THEN** changed paths MUST be limited to the required cron scripts and documentation (plus OpenSpec change files if committed together), with no secrets or runtime lock/log noise
