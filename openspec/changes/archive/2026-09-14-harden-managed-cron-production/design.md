## Context

Production layout (from deploy + ops):

```text
/home/ubuntu/
├── befood-backend/          # PROJECT_DIR (manage.py, scripts/cron/)
└── venv/                    # VENV_DIR — sibling, NOT under project
```

Deploy (`.github/workflows/deploy.yml`, do not edit) already uses:

```bash
PROJECT_DIR="/home/ubuntu/befood-backend"
VENV_DIR="/home/ubuntu/venv"
source "$VENV_DIR/bin/activate"
```

Observed failures:

1. **CRLF** in `scripts/cron/*.sh` → `set: pipefail` / invalid option (partially addressed by `fix-managed-cron-crlf`; must remain enforced).
2. **Wrong venv discovery** → wrappers only check `$PROJECT_DIR/venv` and `$PROJECT_DIR/.venv`, then call bare `python`. On production neither path exists, cron PATH has no project venv → `python: command not found`.

Constraints: no deploy YAML edits; keep managed crontab installer + schedules + Django command names/flags; scripts must work under Linux cron.

## Goals / Non-Goals

**Goals:**

- Wrappers always invoke an absolute Python binary from a discovered venv.
- Discovery matches production sibling layout and local `venv`/`.venv` layouts.
- Loud failure + log line if Python cannot be resolved.
- Preserve flock, logging, `PROJECT_DIR` resolution, executable chmod in installer.
- LF + `.gitattributes` remain correct.
- Docs list verification commands for ops.

**Non-Goals:**

- Editing `.github/workflows/deploy.yml`.
- Changing cron times, markers, or management command APIs.
- Moving production venv under the project directory.
- Adding Celery/systemd replacements for cron.

## Decisions

### D1 — Resolve absolute `PYTHON_BIN`, do not depend on cron PATH

- **Choice:** After discovering a venv root, set `PYTHON_BIN="${VENV_PATH}/bin/python"` and run `"${PYTHON_BIN}" manage.py ...`. Prefer executable existence check over only checking `activate`.
- **Why:** Cron jobs often have a minimal PATH; `source activate` may be skipped silently today, then `python` fails. Absolute path is PATH-independent.
- **Alternatives:** Always `source activate` then `python` — still fragile if activate missing. Hardcode `/home/ubuntu/venv/bin/python` — breaks local/dev and any host with a different layout.

### D2 — Venv discovery order

- **Choice:**

  1. `BEFOOD_VENV` or `VENV_PATH` env override (if set and contains `bin/python`)
  2. `"$(dirname "${PROJECT_DIR}")/venv"` — sibling of project (production)
  3. `"${PROJECT_DIR}/venv"`
  4. `"${PROJECT_DIR}/.venv"`

  If none yield an executable `bin/python`, log error and exit non-zero.
- **Why:** Matches deploy’s `/home/ubuntu/venv` without hardcoding username; keeps local project-local venvs working.
- **Alternatives:** Only sibling — breaks developers with in-project venv. Only override — requires crontab env edits (YAML forbidden / ops friction).

### D3 — Shared resolution pattern in both wrappers (inline, no new shared file required)

- **Choice:** Duplicate a small identical resolution block in `run_auto_deliver.sh` and `run_wallet_threshold_check.sh` (or a tiny sourced `scripts/cron/_common.sh` if preferred for DRY).
- **Preferred:** Extract `scripts/cron/_cron_env.sh` sourced by both wrappers to avoid drift — still LF, no deploy YAML change. Installer does not need to chmod the sourced file for crontab (wrappers remain the crontab entrypoints).
- **Why:** Two wrappers already diverged only on command; venv bugs must stay fixed in both.
- **Alternatives:** Keep duplicated blocks — acceptable for hotfix size if shared file feels heavy.

### D4 — Django env defaults for cron

- **Choice:** If unset, export `DJANGO_ENV=prod` and `DJANGO_SETTINGS_MODULE=core.settings` before invoking manage.py (same as deploy). Do not override if already set (allows dry-run/local testing).
- **Why:** Cron does not inherit deploy shell exports; settings default is already `prod` when unset, but explicit module avoids ambiguity.
- **Alternatives:** Rely only on `core/settings/__init__.py` default — mostly OK, less explicit in logs/ops.

### D5 — Installer stays schedule-only

- **Choice:** `install_managed_cron.sh` continues idempotent BEGIN/END block replace; only ensure LF, `chmod +x` on wrappers, no path hardcoding beyond `${PROJECT_DIR}/scripts/cron/...`.
- **Why:** Absolute paths to wrappers are already derived from script location; venv is wrapper concern.

### D6 — Line endings

- **Choice:** Confirm all `scripts/cron/*.sh` (and `_cron_env.sh` if added) are LF; keep `.gitattributes` `*.sh text eol=lf`; renormalize if needed.
- **Why:** Prevents recurrence of the pipefail failure.

## Risks / Trade-offs

- **[Risk] Sibling `../venv` exists but is wrong/incomplete on a misconfigured host** → **Mitigation:** Prefer override env; check `bin/python` is executable; fail loud with path attempted in log.
- **[Risk] Local Windows still checks out scripts with editors forcing CRLF** → **Mitigation:** `.gitattributes` + verify CR=0 before ship.
- **[Risk] Shared `_cron_env.sh` not executable / missing after partial deploy** → **Mitigation:** Source by absolute path next to wrappers; fail if missing.
- **[Risk] `DJANGO_ENV=prod` default surprises local manual runs** → **Mitigation:** Only set when unset; document `DJANGO_ENV=local` for local testing.

## Migration Plan

1. Land LF + wrapper/venv fix on `main`.
2. Deploy pulls code; existing step 9 reinstalls managed crontab (unchanged YAML).
3. Manually smoke: `bash scripts/cron/run_wallet_threshold_check.sh` and `bash scripts/cron/run_auto_deliver.sh lunch`; inspect logs.
4. Rollback: revert commit and re-run installer; or temporarily remove managed block from crontab.

## Open Questions

- None blocking. Optional later: CI check for `\r` in `scripts/**/*.sh`.
