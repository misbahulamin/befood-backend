## 1. Analysis lock-in & settings

- [x] 1.1 Confirm shared helpers to reuse: `mark_delivery`, `charge_delivered_meal` (indirect), `live_delivery_q`, meal-off business timezone helpers
- [x] 1.2 Add optional settings flag `AUTO_MEAL_DELIVERY_ENABLED` (default True) and document meal-off deadline vs cron schedule in `orders/docs/backend/auto-meal-delivery.md`

## 2. Auto-delivery domain service

- [x] 2.1 Implement `orders/services/auto_meal_delivery.py` with candidate queryset (`service_date`, `meal_period`, `scheduled`, `live_delivery_q`)
- [x] 2.2 Implement `run_auto_delivery(...)` looping candidates, calling `mark_delivery(..., 'delivered', marked_by=None, note=...)`, aggregating success/failure/idempotent counts with per-slot try/except
- [x] 2.3 Add process lock (file flock or equivalent) so overlapping cron runs exit safely

## 3. Delivery notification (shared)

- [x] 3.1 Implement `notify_meal_delivered(delivery)` using existing FCM token resolution + `send_to_tokens` (best-effort, never raises into callers)
- [x] 3.2 Wire notification after successful `mark_delivery` for both admin mark endpoints (order + subscription) and the auto-delivery runner so manual and cron stay consistent
- [x] 3.3 Ensure skip path does not send delivered notification

## 4. Management command

- [x] 4.1 Add `orders/management/commands/auto_deliver_meals.py` with `--meal-period lunch|dinner`, `--date YYYY-MM-DD`, `--dry-run`
- [x] 4.2 Resolve default `--date` from Asia/Dhaka business “today”; print structured summary to stdout for cron logs

## 5. Managed cron packaging (no YAML edits)

- [x] 5.1 Add `scripts/cron/run_auto_deliver.sh` (venv activate, manage.py invoke, log append)
- [x] 5.2 Add `scripts/cron/install_managed_cron.sh` with tagged idempotent crontab block (lunch 15:00, dinner 23:00, `CRON_TZ=Asia/Dhaka` or equivalent)
- [x] 5.3 Document install/verify/rollback in the backend doc; explicitly note `.github/workflows/deploy.yml` must not be changed

## 6. Tests

- [x] 6.1 Unit/integration tests: meal-off skipped excluded; scheduled live included; wallet charge on success; insufficient wallet isolates failure; dry-run mutates nothing; lunch job ignores dinner
- [x] 6.2 Tests: idempotent second run; notification attempted on deliver and not on skip; notification failure does not revert delivered
- [x] 6.3 Smoke-test installer script syntax (`bash -n`) where available

## 7. Frontend / ops notes (no FE code required)

- [x] 7.1 Record in backend doc how admin subscription detail + delivery board behave after cron (buttons hide when not `scheduled`; refetch on focus)
- [x] 7.2 Optional follow-up note only: expose `marked_at` / system note in admin UI later — not part of implement checklist unless product asks
