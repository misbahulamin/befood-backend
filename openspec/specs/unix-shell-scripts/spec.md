# unix-shell-scripts Specification

## Purpose
TBD - created by archiving change fix-managed-cron-utc-schedules. Update Purpose after archive.
## Requirements
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

### Requirement: Production shell scripts use LF line endings

Shell scripts intended to run on Linux production hosts (under `scripts/`, including managed cron wrappers and installers) MUST use Unix LF (`\n`) line endings only. They MUST NOT contain carriage-return (`\r`) characters that would corrupt bash option parsing or path tokens.

#### Scenario: Managed cron installer parses bash options cleanly

- **WHEN** a Linux host executes `bash scripts/cron/install_managed_cron.sh`
- **THEN** the script MUST NOT fail on `set -euo pipefail` (or equivalent) due to a trailing `\r`, and MUST proceed to update the managed crontab block when crontab is available

#### Scenario: Cron wrapper scripts are LF-normalized

- **WHEN** `scripts/cron/run_auto_deliver.sh` and `scripts/cron/run_wallet_threshold_check.sh` are present in the repository
- **THEN** each file MUST use LF-only line endings so production cron invocations via bash succeed

### Requirement: Repository enforces LF for shell scripts

The repository MUST declare Git attributes so `*.sh` files are treated as text with `eol=lf`, preventing Windows checkouts/commits from reintroducing CRLF into production shell scripts.

#### Scenario: gitattributes declares LF for shell scripts

- **WHEN** a contributor clones or checks out the repository on any OS
- **THEN** Git MUST apply `*.sh text eol=lf` (or an equivalent rule covering production shell scripts) so shell script working-tree files use LF endings

