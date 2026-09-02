## Why

Admin currently marks each meal slot `delivered` by hand on the subscription detail / kitchen board; that click is the only path that updates status and deducts the wallet. Operators should not repeat that for every non–meal-off customer twice a day. Automating the same delivery mark at fixed lunch/dinner times removes manual load while keeping wallet charges, idempotency, and eligibility rules identical to the existing admin flow.

## What Changes

- Add a **scheduled auto-delivery** job that selects today's (or the target service date's) `scheduled` lunch/dinner slots for live orders/subscriptions where the customer did **not** meal-off, then runs the **same** delivery mark path as admin `POST .../deliveries/{id}/mark` with `status=delivered`.
- Reuse `orders.services.order_delivery.mark_delivery` (and thus `charge_delivered_meal` / wallet ledger / Onahar credit) — **no duplicate deduct/status logic**.
- Add **delivery notification** when a meal is marked delivered (shared helper so cron and manual mark stay consistent; today mark does not push).
- Add Django **management commands** for lunch and dinner auto-delivery (dry-run, date override, per-slot error isolation).
- Add **managed production cron installer** under `scripts/cron/` so deploy's existing hook installs/persists crontab entries **without changing** `.github/workflows/deploy.yml`.
- Document operator expectations: meal-off deadlines remain `MealOffSettings` (not hard-coded 03:00); cron times are 15:00 lunch and 23:00 dinner in `Asia/Dhaka` (configurable via crontab).
- Frontend: **no required UI change** for automation; optional later badge for system vs admin mark is out of scope unless needed for ops clarity.

## Capabilities

### New Capabilities

- `auto-meal-delivery`: Batch selection of eligible `OrderDelivery` slots and automated mark-as-delivered with wallet charge, logging, and failure isolation for lunch/dinner schedules.
- `meal-delivery-notification`: Push (and recorded) notification to the customer when a meal slot becomes `delivered`, shared by manual admin mark and cron.
- `managed-cron-install`: Repository-owned cron definitions + `install_managed_cron.sh` that idempotently installs production jobs after deploy/pull without editing CI YAML.

### Modified Capabilities

- _(none — existing meal-off / mark-delivery API contracts stay unchanged; automation calls the same service layer)_

## Impact

- **Backend:** `orders/services/` (thin batch orchestrator), new `orders/management/commands/`, optional notification helper under `notifications/services/`, `scripts/cron/*`, tests under `orders/tests/` (+ notification tests if added).
- **APIs:** No new public mark contract required; admin `POST /api/v1/web/subscriptions/{id}/deliveries/{id}/mark` and order mark endpoints keep current request/response. Notification is a side effect of successful deliver.
- **Frontend (`befood-frontend`):** Admin subscription page already refetches on focus; auto-delivered slots simply stop showing Delivered/Skip. No mandatory FE work for MVP.
- **Deploy:** Relies on existing deploy step that runs `scripts/cron/install_managed_cron.sh` when present; YAML must not be modified.
- **Ops risk:** Insufficient wallet / missing slot price leave slot `scheduled` (same as manual 422); cron must log and continue. Overlap/lock file needed so concurrent runs do not double-process.
