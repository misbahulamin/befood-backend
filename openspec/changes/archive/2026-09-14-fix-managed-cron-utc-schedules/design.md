## Context

BeFood production EC2 host timezone is `Etc/UTC`. Ubuntu cron evaluates minute/hour fields in UTC. The current managed installer still writes:

```text
CRON_TZ=Asia/Dhaka
0 15 * * * …/run_auto_deliver.sh lunch
0 23 * * * …/run_auto_deliver.sh dinner
0 8 * * * …/run_wallet_threshold_check.sh
0 20 * * * …/run_wallet_threshold_check.sh
```

`CRON_TZ` is unreliable on this host. Manual `bash scripts/cron/run_auto_deliver.sh lunch` already succeeds (Django logic OK). Prior hardening covers LF endings and venv discovery; this change hardens schedule timezone semantics, locks the managed-block comment contract, re-audits Python resolution, updates docs, and defines validation gates.

Hard constraints:

- Do not edit `.github/workflows/deploy.yml`.
- Do not change management commands, `mark_delivery`, wallet charging, or notification logic.
- Keep flock, `tmp/locks/`, and log paths.
- Keep `# BEGIN/END BEFOOD-MANAGED` idempotent replace.

## Goals / Non-Goals

**Goals:**

- Install UTC crontab hours that fire at Asia/Dhaka business times without `CRON_TZ`.
- Managed block comments must state host cron = UTC and business timezone = Asia/Dhaka.
- Wrappers never call bare `python`; always absolute `PYTHON_BIN` with success-log line containing `PYTHON_BIN=…`.
- Preserve flock + existing log files.
- Docs + `bash -n` / no-CRLF / clean git tree ready for commit.

**Non-Goals:**

- Django `TIME_ZONE`, meal-off business TZ logic, management command APIs.
- Deploy / supervisor / nginx changes.
- Automating TZ math at install time.
- Changing lock/log file names or removing concurrency guards.

## Decisions

### 1. Hard-code UTC hours; exact managed-block comments

**Choice:** Static UTC schedules and required comments:

```text
# BEGIN BEFOOD-MANAGED
# Host cron timezone: UTC
# Business timezone: Asia/Dhaka
0 9 * * * ${PROJECT_DIR}/scripts/cron/run_auto_deliver.sh lunch
0 17 * * * ${PROJECT_DIR}/scripts/cron/run_auto_deliver.sh dinner
0 2 * * * ${PROJECT_DIR}/scripts/cron/run_wallet_threshold_check.sh
0 14 * * * ${PROJECT_DIR}/scripts/cron/run_wallet_threshold_check.sh
# END BEFOOD-MANAGED
```

| Job | Asia/Dhaka | UTC |
|-----|------------|-----|
| Lunch auto-deliver | 15:00 | `0 9 * * *` |
| Dinner auto-deliver | 23:00 | `0 17 * * *` |
| Wallet morning | 08:00 | `0 2 * * *` |
| Wallet evening | 20:00 | `0 14 * * *` |

**Alternatives rejected:** Keep `CRON_TZ`; change host TZ to Asia/Dhaka; switch to systemd timers.

### 2. Idempotent replace strips old `CRON_TZ` / BD hours

**Choice:** Existing awk strip between markers remains the sole mechanism; re-run replaces the whole block so old `CRON_TZ` and hours `15`/`23`/`8`/`20` disappear from the managed section. Running twice must not duplicate jobs.

### 3. Absolute Python discovery (no bare `python`)

**Choice:** Keep / confirm `_cron_env.sh` order:

1. `${BEFOOD_VENV}/bin/python`
2. `${VENV_PATH}/bin/python`
3. `$(dirname PROJECT_DIR)/venv/bin/python` (e.g. `/home/ubuntu/venv/bin/python`)
4. `${PROJECT_DIR}/venv/bin/python`
5. `${PROJECT_DIR}/.venv/bin/python`

Wrappers MUST invoke `"${PYTHON_BIN}" manage.py …` only. Missing interpreter → clear error + non-zero exit. Success log MUST include `PYTHON_BIN=/absolute/path`.

Command contracts unchanged:

- `check_wallet_balance_thresholds`
- `auto_deliver_meals --meal-period lunch|dinner`

### 4. Preserve locking and logging paths

**Choice:** Do not remove flock or change:

- `logs/cron-wallet-threshold-check.log`
- `logs/cron-auto-deliver-lunch.log` / `logs/cron-auto-deliver-dinner.log`
- `tmp/locks/cron-wrapper-*.lock`

### 5. Docs + validation as release gates

**Choice:** Update both backend docs with the three-layer timezone story. Before commit readiness: `bash -n` on three scripts; `grep` for `\r` must be empty; `git status` / `git diff --stat` show only required paths (no `.env`, `logs/`, `tmp/locks/`, media/test noise).

## Risks / Trade-offs

- **[Risk] Asia/Dhaka offset change** → Mitigation: conversion table in installer comments + docs; update four hours.
- **[Risk] Stale crontab until reinstall** → Mitigation: deploy already runs installer; document manual `bash scripts/cron/install_managed_cron.sh`.
- **[Risk] Operators misread UTC hours as BD** → Mitigation: required managed-block comments + docs.
- **[Trade-off] Crontab less “local readable”** → Accepted for reliability.

## Migration Plan

1. Land script + doc changes.
2. Deploy or SSH → code sync → `install_managed_cron.sh` replaces managed block.
3. Verify: `crontab -l` has UTC hours, host/business comments, no `CRON_TZ`; smoke wrappers if needed.
4. Rollback: prefer forward-fix of hours; avoid restoring `CRON_TZ`.

## Open Questions

- None — UTC table and “no `CRON_TZ`” are fixed by production findings.
