## 1. Normalize cron scripts

- [x] 1.1 Convert `scripts/cron/install_managed_cron.sh` to LF-only line endings (remove all `\r`)
- [x] 1.2 Convert `scripts/cron/run_auto_deliver.sh` to LF-only line endings
- [x] 1.3 Convert `scripts/cron/run_wallet_threshold_check.sh` to LF-only line endings

## 2. Enforce via Git attributes

- [x] 2.1 Add root `.gitattributes` with `*.sh text eol=lf`
- [x] 2.2 Renormalize / stage shell scripts so the Git blob stores LF (e.g. `git add --renormalize scripts/cron/*.sh` or equivalent rewrite)

## 3. Verify

- [x] 3.1 Confirm each `scripts/cron/*.sh` has zero `\r` bytes
- [x] 3.2 Run `bash -n` on all three cron scripts (or equivalent syntax check)
- [x] 3.3 Note in deploy/docs if needed: re-run production deploy and expect step 9 to succeed without editing `deploy.yml`
