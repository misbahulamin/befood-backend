## Why

Production deploys fail when EC2 has local modifications to tracked cron scripts: `git pull --ff-only origin main` aborts with “local changes would be overwritten by merge,” so migrations, cron install, and service restarts never run. Prior cron hardening (LF, absolute venv Python) is already on `main`, but the deploy workflow still uses a non-deterministic pull strategy and production may still hold a dirty tree from earlier manual/CRLF edits. We need one production-safe pipeline that always ships `origin/main` without relying on a clean working tree or PATH-dependent `python`.

## What Changes

- Update `.github/workflows/deploy.yml` to sync the server to `origin/main` deterministically (prefer `git fetch` + `git reset --hard origin/main` after logging dirty state), instead of `git pull --ff-only`.
- Before hard reset: show `git status` / dirty paths so operators can see what server-local edits are discarded; do **not** stash-and-restore tracked files (that reintroduces drift).
- Keep untracked production secrets and runtime artifacts safe (`.env`, `logs/`, sockets, media) because they are not overwritten by `git reset --hard`.
- Audit and lock managed cron runtime: LF + `.gitattributes`, absolute `PYTHON_BIN` via `_cron_env.sh`, flock/logging/exit behavior, idempotent `install_managed_cron.sh` with existing Asia/Dhaka schedules and `BEGIN`/`END BEFOOD-MANAGED` markers.
- Add/refresh verification steps (local `bash -n` / no CRLF; production clean tree, crontab, manual wrapper smoke).
- **No** Django business-logic changes, **no** cron schedule changes, **no** removal of wallet-threshold or auto-deliver functionality.

## Capabilities

### New Capabilities

- `production-deploy-sync`: GitHub Actions SSH deploy always brings `/home/ubuntu/befood-backend` to match `origin/main` even when tracked files are dirty, then continues the existing migrate / collectstatic / cron install / supervisor / nginx sequence.
- `managed-cron-runtime`: Production cron wrappers resolve project root and absolute venv Python (sibling `/home/ubuntu/venv`), run existing management commands with flock/logging, and remain installable via the managed crontab installer (absorbs prior hardening into an auditable contract).
- `unix-shell-scripts`: Shell scripts under `scripts/` use LF line endings and repo `.gitattributes` (`*.sh text eol=lf`) so Linux bash can execute them.

### Modified Capabilities

- (none — these capabilities are not yet in `openspec/specs/`)

## Impact

- **Files:** `.github/workflows/deploy.yml`; audit/touch only as needed: `scripts/cron/*.sh`, `.gitattributes`, cron-related ops docs under `orders/docs/backend/`
- **Systems:** GitHub Actions → EC2 SSH deploy; production crontab under `ubuntu`
- **APIs / Django domain logic:** None
- **Risk:** Hard reset discards uncommitted edits to **tracked** files on the server (intentional — `main` is source of truth). Untracked secrets/logs remain. First successful deploy after this change clears the dirty cron scripts that currently block pulls.
