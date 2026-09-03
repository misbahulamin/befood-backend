## Why

Production managed cron is failing end-to-end: first CRLF broke the installer (`set: pipefail`), and after that wrappers still fail with `python: command not found` because they only look for `PROJECT_DIR/venv` while production uses sibling `/home/ubuntu/venv` (as in deploy). Cron PATH is minimal, so activate-or-fail silently leaves bare `python` unresolved. We need a durable, production-safe fix for line endings and venv/Python resolution without changing deploy YAML, schedules, or Django commands.

## What Changes

- Keep/complete LF normalization for all `scripts/cron/*.sh` and root `.gitattributes` (`*.sh text eol=lf`).
- Rewrite cron wrappers to resolve an absolute Python interpreter (never rely on cron PATH alone).
- Discover venv in production-safe order: env override → sibling `../venv` (matches deploy) → `PROJECT_DIR/venv` → `PROJECT_DIR/.venv`.
- Fail loudly with a logged error if no usable Python is found (instead of falling through to system `python`).
- Ensure wrappers `cd` to `PROJECT_DIR`, keep flock + log append behavior, and set production Django env vars when missing (aligned with deploy: `DJANGO_ENV=prod`, `DJANGO_SETTINGS_MODULE=core.settings`).
- Update backend cron docs with verification commands and production layout notes.
- **No** changes to `.github/workflows/deploy.yml`, cron schedules, management command names/flags, or managed-block markers.

## Capabilities

### New Capabilities

- `managed-cron-runtime`: Production cron wrappers resolve project root and absolute venv Python, run existing management commands with flock/logging, and remain installable via the existing managed crontab installer.
- `unix-shell-scripts`: Shell scripts under `scripts/` use LF line endings and repo `.gitattributes` (`*.sh text eol=lf`) so Linux bash can execute them (continues / absorbs `fix-managed-cron-crlf`).

### Modified Capabilities

- (none)

## Impact

- **Files:** `scripts/cron/run_auto_deliver.sh`, `scripts/cron/run_wallet_threshold_check.sh`, `scripts/cron/install_managed_cron.sh` (LF/chmod only if needed), `.gitattributes`, `orders/docs/backend/auto-meal-delivery.md`, `orders/docs/backend/wallet-balance-thresholds.md`
- **Systems:** Production crontab jobs on `/home/ubuntu` (sibling venv layout)
- **APIs / Django domain logic:** None
- **Prior change:** Supersedes incomplete production readiness of `fix-managed-cron-crlf` (CRLF-only) by also fixing venv/PATH
