## Context

Inspected current production-facing code (no assumptions beyond repo + reported EC2 failures):

| Area | Current state on `main` |
|------|-------------------------|
| `.github/workflows/deploy.yml` | SSH deploy: `git fetch` → `checkout main` → **`git pull --ff-only origin main`** → activate `/home/ubuntu/venv` → pip/migrate/collectstatic → `install_managed_cron.sh` → nginx test → supervisor restart → health checks |
| Dirty-tree failure | EC2 has local mods to tracked `scripts/cron/*.sh`; `pull --ff-only` refuses to overwrite → deploy aborts before cron/services |
| Cron wrappers | Already hardened: `_cron_env.sh` resolves sibling `../venv` → absolute `PYTHON_BIN`; flock + logs; LF + `.gitattributes` |
| Installer | Idempotent `# BEGIN/END BEFOOD-MANAGED`, Asia/Dhaka schedules unchanged |
| Older commented workflow | Already used `git reset --hard origin/main` (correct pattern; not active) |

Production layout (from deploy + ops):

```text
/home/ubuntu/
├── befood-backend/   # git working tree + manage.py + scripts/
└── venv/             # sibling venv (not under project)
```

Constraint from product: always deploy latest `main`; do not treat server edits to tracked files as source of truth; do not break Django logic or cron schedules.

## Goals / Non-Goals

**Goals:**

- Make deploy sync to `origin/main` even when tracked files are dirty.
- Log what will be discarded before reset (operator visibility).
- Preserve untracked production artifacts (`.env`, logs, sockets).
- Re-audit cron LF / venv / installer / wrappers; fix only real gaps.
- Document local + production verification commands.

**Non-Goals:**

- Changing Django management command logic or wallet/auto-deliver domain behavior.
- Changing cron schedules or managed-block markers.
- Moving venv under the project directory.
- Replacing cron with Celery/systemd.
- Stashing and restoring tracked server edits after deploy.

## Decisions

### D1 — Deterministic sync: `fetch` + `reset --hard origin/main` (not stash)

- **Choice:** Replace `git pull --ff-only` with:

  ```bash
  git fetch origin main
  git checkout main
  # Log dirty state for ops visibility (non-fatal)
  git status --short || true
  git reset --hard origin/main
  git clean -fd --exclude=.env --exclude='logs' --exclude='tmp' --exclude='*.sock' --exclude='media' || true
  # Optional: verify
  test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
  ```

  Tune `git clean` excludes carefully so we never delete secrets or runtime dirs. Prefer a **narrow** clean (or skip clean entirely if only tracked dirt is the problem). **Minimum required fix:** `reset --hard origin/main` after fetch — that alone fixes the reported pull failure.

- **Why preferred over stash:** Stash preserves local tracked edits and tempts `stash pop`, reintroducing drift and the same conflict next deploy. Production tracked code MUST equal GitHub `main`.

- **Why preferred over `pull --ff-only`:** Fast-forward pull requires a clean overlapping tree; server-side cron edits are exactly the conflict case we see.

- **Why preferred over `checkout --force` alone:** Without resetting to `origin/main`, local commits or divergent history can remain; `reset --hard origin/main` is explicit.

- **“Do not blindly overwrite important production changes”:** Important production state lives in **untracked** files (`.env`) and infrastructure (supervisor/nginx configs outside the repo). Tracked cron scripts must come from git. Logging dirty paths before reset satisfies the audit trail without keeping bad local forks.

### D2 — Keep deploy venv activation; cron keeps absolute Python

- **Choice:** Deploy job continues `source /home/ubuntu/venv/bin/activate` then `python manage.py ...`. Cron wrappers continue using `"${PYTHON_BIN}"` from `_cron_env.sh` (never bare `python` on cron PATH).
- **Why:** Different execution contexts. Deploy SSH session has controlled activate; cron does not. Absolute path remains mandatory for wrappers.
- **Alternative rejected:** Hardcoding only `/home/ubuntu/venv/bin/python` in deploy — unnecessary if activate already works; wrappers already discover sibling venv.

### D3 — Cron audit is verify-first, edit-only-on-gap

- **Choice:** Treat current `scripts/cron/*` + `.gitattributes` as the intended baseline (from prior hardening). Implementation tasks: byte-check LF, `bash -n`, confirm discovery order and schedules; patch only if audit finds regressions.
- **Why:** Avoid churn that reintroduces CRLF or schedule drift. User asked for complete audit + production-safe fix, not a rewrite.

### D4 — Installer invocation unchanged in deploy sequence

- **Choice:** After successful git sync, keep step: `bash "$PROJECT_DIR/scripts/cron/install_managed_cron.sh"`. Schedules stay:

  | Job | Cron (Asia/Dhaka) |
  |-----|-------------------|
  | Auto-deliver lunch | `0 15 * * *` |
  | Auto-deliver dinner | `0 23 * * *` |
  | Wallet threshold | `0 8 * * *` and `0 20 * * *` |

- **Why:** Separates “get code” from “refresh crontab”; idempotent installer already safe to re-run every deploy.

### D5 — No Django / schedule / feature removals

- **Choice:** Explicit non-goals enforced in tasks checklist.
- **Why:** User requirement; reduces blast radius to deploy sync + cron ops hygiene.

## Risks / Trade-offs

- **[Risk] Hard reset discards useful uncommitted edits on tracked files** → **Mitigation:** Log `git status --short` before reset; require all intentional changes via PR to `main`. Document in deploy logs.
- **[Risk] Over-aggressive `git clean -fd` deletes needed untracked files** → **Mitigation:** Prefer **no clean** or tightly excluded clean; default recommendation is `reset --hard` only unless audit shows untracked junk blocking deploy.
- **[Risk] First deploy after fix still fails if SSH/secrets wrong** → **Mitigation:** Out of scope; unchanged from today once git sync succeeds.
- **[Risk] CRLF reintroduced on Windows contributor machines** → **Mitigation:** Keep `.gitattributes` `*.sh text eol=lf`; CI/local `bash -n` + CR byte check in tasks.
- **[Risk] Wrong sibling venv on non-standard hosts** → **Mitigation:** `_cron_env.sh` override via `BEFOOD_VENV` / `VENV_PATH`; loud failure if missing.

## Migration Plan

1. Merge this change to `main` (deploy.yml + any cron audit fixes).
2. Trigger GitHub Actions deploy (push or `workflow_dispatch`).
3. Deploy script fetches and hard-resets over dirty cron files → tree matches `origin/main`.
4. Installer refreshes managed crontab; gunicorn/nginx steps proceed.
5. Ops smoke: `git status` clean; `crontab -l` shows managed block; manual wrapper runs write logs.
6. **Rollback:** Revert deploy.yml commit on `main` and redeploy (returns to pull behavior — not recommended if tree dirty again). Cron scripts remain on last good `main`.

## Open Questions

- None blocking implementation. Optional: whether to enable a narrow `git clean` — **default no**; only add if production shows untracked tracked-name conflicts (rare).
