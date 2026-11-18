# Unassigned delivery subscribers digest (backend)

## Purpose

Twice-daily admin email listing **active** meal subscribers whose
`CustomerProfile.delivery_sub_location` is still null, so ops can assign
zone hierarchy before riders miss them.

Unassigned predicate = `delivery_sub_location IS NULL` (mirrored
`delivery_location` alone does **not** count as assigned). Cancelled
subscriptions are excluded.

## Command

```bash
python manage.py send_unassigned_delivery_digest [--dry-run] [--slot evening|night]
```

| Flag | Effect |
|------|--------|
| `--dry-run` | Report `candidate_count` only; **no** email |
| `--slot evening\|night` | Log label only; does not filter candidates |

Empty candidate lists do **not** send email. Confirm empty runs via cron /
command logs (`candidate_count=0`, `email_sent=false`), not the inbox.

## Schedules (managed cron)

| Business (Asia/Dhaka) | UTC crontab | Wrapper slot |
|-----------------------|-------------|--------------|
| 18:00 | `0 12 * * *` | `evening` |
| 22:00 | `0 16 * * *` | `night` |

Host cron is UTC. **`CRON_TZ` is not used.** Installer:
`scripts/cron/install_managed_cron.sh` (also keeps auto-deliver + wallet jobs).

| Piece | Path |
|-------|------|
| Wrapper | `scripts/cron/run_unassigned_delivery_digest.sh` |
| Shared env | `scripts/cron/_cron_env.sh` (absolute venv `PYTHON_BIN`) |
| Log | `logs/cron-unassigned-delivery-digest.log` |

Each non-empty run emails the **full current backlog** (not a since-last-run
delta). Empty runs still execute and log; they simply skip SMTP.

## Email

- Recipients: `resolve_funding_admin_emails()` (verified ADMIN + active superusers)
- Columns: Name, Phone, Subscription Time (`created_at` Asia/Dhaka), Email (or `N/A`)
- Subject example (only when `candidate_count >= 1`):
  - `[BeFood] Unassigned delivery subscribers (N)`

## Service

`delivery_zones.services.unassigned_digest.run_unassigned_delivery_digest`

## Dry-run / smoke

```bash
python manage.py send_unassigned_delivery_digest --dry-run
bash scripts/cron/run_unassigned_delivery_digest.sh evening
tail -n 50 logs/cron-unassigned-delivery-digest.log
```

## How to verify

- `delivery_zones.tests.test_unassigned_digest` — query membership, email columns,
  empty skip / dry-run, command paths, installer UTC schedule smoke
- `bash -n scripts/cron/run_unassigned_delivery_digest.sh scripts/cron/install_managed_cron.sh`
