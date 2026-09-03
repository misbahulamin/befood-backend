## Why

Production deploy fails at step 9 (“Updating managed cron jobs”) because `scripts/cron/*.sh` are checked out with Windows CRLF line endings. Bash then treats `pipefail\r` as an invalid `set` option and exits with code 2, aborting the rest of the deploy (nginx test / Gunicorn restart never run).

## What Changes

- Convert all `scripts/cron/*.sh` files to Unix LF line endings.
- Add a root `.gitattributes` rule so shell scripts (and related deploy helpers) are always checked out as LF on every platform.
- Document a quick verification check (`bash -n` / byte check) so future cron wrappers stay deploy-safe.
- **No** changes to `.github/workflows/deploy.yml` (existing constraint for managed cron).

## Capabilities

### New Capabilities

- `unix-shell-scripts`: Production shell scripts under `scripts/` MUST use LF line endings and remain runnable by bash on Linux deploy hosts.

### Modified Capabilities

- (none)

## Impact

- **Files:** `scripts/cron/install_managed_cron.sh`, `scripts/cron/run_auto_deliver.sh`, `scripts/cron/run_wallet_threshold_check.sh`, new `.gitattributes`
- **Systems:** GitHub Actions SSH deploy step that runs `bash .../install_managed_cron.sh`
- **APIs / Django:** None
- **Risk:** Low; content of cron schedules is unchanged—only line endings and repo hygiene
