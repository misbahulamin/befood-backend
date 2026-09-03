## ADDED Requirements

### Requirement: Deploy syncs production tree to origin/main deterministically

The production deploy workflow MUST update `/home/ubuntu/befood-backend` to match `origin/main` using a deterministic Git strategy that succeeds even when tracked files have local modifications. The workflow MUST NOT rely solely on `git pull --ff-only` (or equivalent merge/pull) as the only update mechanism when a dirty working tree can block deploying `main`.

#### Scenario: Dirty tracked cron scripts do not block deploy

- **WHEN** production has local modifications to tracked files such as `scripts/cron/*.sh` and GitHub Actions runs the deploy job against `main`
- **THEN** the deploy MUST still bring the working tree to the commit pointed at by `origin/main` without aborting solely due to “local changes would be overwritten”

#### Scenario: Preferred sync strategy is fetch plus hard reset

- **WHEN** the deploy updates application source on the EC2 host
- **THEN** it MUST `git fetch` the remote `main` ref and reset the checked-out branch hard to `origin/main` (or an equivalent force-sync that yields the same tree), and MUST NOT stash-and-restore tracked local edits as the primary strategy

### Requirement: Dirty state is visible before discard

Before discarding local tracked changes, the deploy MUST log enough Git status information for operators to see which paths will be overwritten (for example `git status --short` or equivalent). Untracked production secrets and runtime artifacts that are not part of the Git tree (such as `.env`, application logs, and sockets) MUST remain outside the hard-reset discard of tracked content.

#### Scenario: Operators can see discarded paths in deploy logs

- **WHEN** a deploy runs while the working tree has modified tracked files
- **THEN** the deploy log MUST include a status listing of dirty paths before the hard reset completes

#### Scenario: Untracked env file survives sync

- **WHEN** `/home/ubuntu/befood-backend/.env` exists as an untracked file and deploy resets tracked files to `origin/main`
- **THEN** the `.env` file MUST still be present after the sync step (hard reset does not delete untracked files)

### Requirement: Post-sync deploy steps continue unchanged in purpose

After a successful sync to `origin/main`, deploy MUST continue to install dependencies in the production venv, run Django check/migrate/collectstatic, invoke `scripts/cron/install_managed_cron.sh` when present, validate nginx, restart Gunicorn via supervisor, and perform the existing health checks. Sync strategy changes MUST NOT remove managed cron installation or application restart steps.

#### Scenario: Cron installer still runs after sync

- **WHEN** deploy successfully syncs to `origin/main` and `scripts/cron/install_managed_cron.sh` exists
- **THEN** deploy MUST execute that installer before claiming deployment success
