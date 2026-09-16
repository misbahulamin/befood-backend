## Why

Production EC2 runs Ubuntu cron in **UTC** (`Etc/UTC`). The managed installer still emits `CRON_TZ=Asia/Dhaka` with Bangladesh-hour schedules (`15:00` / `23:00` lunch/dinner, `08:00` / `20:00` wallet), but `CRON_TZ` is unreliable here, so jobs miss intended Asia/Dhaka wall times. Manual wrapper runs already succeed (Django auto-delivery logic is correct); only crontab scheduling, wrapper env audit, docs, and validation need hardening.

## What Changes

- **Installer:** Remove `CRON_TZ=Asia/Dhaka`. Emit UTC schedules with explicit host/business timezone comments inside `# BEGIN/END BEFOOD-MANAGED`. Idempotently replace any old managed block (including old `CRON_TZ` / BD-hour lines). Keep absolute wrapper paths and `chmod +x`.
  - Lunch 15:00 BD → `0 9 * * *` UTC
  - Dinner 23:00 BD → `0 17 * * *` UTC
  - Wallet 08:00 / 20:00 BD → `0 2 * * *` / `0 14 * * *` UTC
- **Wrappers / env:** Audit `_cron_env.sh` + runners so they **never** invoke bare `python manage.py …`; always use absolute `PYTHON_BIN` from discovery order (env overrides → sibling `../venv` → project `venv` / `.venv`); fail non-zero if missing; log `PYTHON_BIN=…` on success. Keep flock, `tmp/locks/`, and existing log paths.
- **Docs:** Document EC2 UTC host, UTC crontab fields, Asia/Dhaka business meaning, and intentional non-use of `CRON_TZ`.
- **Validation:** `bash -n` on installer + wrappers; no CRLF in `scripts/cron/*.sh`; clean `git diff` / `git status` with only required files.
- **Out of scope:** Django delivery services, `mark_delivery`, wallet charging, notifications, management commands, `.github/workflows/deploy.yml`.

## Capabilities

### New Capabilities

- `managed-cron-runtime`: UTC managed crontab (no `CRON_TZ`), absolute venv Python with logged `PYTHON_BIN`, preserved flock/logging, idempotent deploy-compatible installer.
- `unix-shell-scripts`: `scripts/cron/*.sh` stay LF-only and pass `bash -n`.

### Modified Capabilities

- (none — these capabilities are not yet in `openspec/specs/`)

## Impact

- **Files:** `scripts/cron/install_managed_cron.sh`, `scripts/cron/_cron_env.sh` (if gaps), `scripts/cron/run_auto_deliver.sh`, `scripts/cron/run_wallet_threshold_check.sh`, `orders/docs/backend/auto-meal-delivery.md`, `orders/docs/backend/wallet-balance-thresholds.md`
- **Systems:** Production crontab for `ubuntu` after deploy or manual `bash scripts/cron/install_managed_cron.sh`
- **Do not touch:** `.env`, `logs/`, `tmp/locks/`, `media/`, test fixtures, deploy YAML, Django domain code
