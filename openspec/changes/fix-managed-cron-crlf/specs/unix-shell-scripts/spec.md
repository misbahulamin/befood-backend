## ADDED Requirements

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
