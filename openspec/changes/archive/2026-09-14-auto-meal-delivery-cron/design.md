## Context

### Current manual flow (backend + admin frontend)

Admin subscription detail (`/admin/subscriptions/:subscriptionId`) and kitchen board call:

```http
POST /api/v1/web/subscriptions/{subscription_public_id}/deliveries/{delivery_public_id}/mark
{ "status": "delivered", "note"?: "..." }
```

That hits `AdminSubscriptionViewSet.mark_delivery` → `orders.services.order_delivery.mark_delivery`, which atomically:

1. Locks the `OrderDelivery` row
2. Rejects cancelled parents / terminal conflicts; idempotent if already `delivered`
3. Sets `status=delivered`, `marked_by`, `marked_at`
4. Calls `charge_delivered_meal` (published slot final price → `debit_wallet` with key `meal-delivery:{public_id}`)
5. Best-effort Onahar `credit_for_delivery`
6. Completes parent order when all slots done

**Clarification vs product language:** There is no per-meal `isVerified` on `OrderDelivery`. Admin “verification” on this page is not a meal gate; the actionable control is **Delivered** / **Skip** for `scheduled` slots. Customer meal-off sets `status=skipped` + `skip_source=customer` before the meal-off deadline (`MealOffSettings`, default lunch previous-day 23:59 / dinner same-day 14:00 in `Asia/Dhaka` — **not** hard-coded 03:00).

**Gap:** `mark_delivery` does **not** send FCM today. Product wants a customer notification on auto-delivery; design makes notification a shared post-success side effect so manual and cron stay aligned.

**Deploy:** `.github/workflows/deploy.yml` already runs `$PROJECT_DIR/scripts/cron/install_managed_cron.sh` when the file exists. The script and `scripts/cron/` tree are **missing** in-repo. Constraint: **do not edit** that YAML.

### Stakeholders

- Kitchen / admin ops (stop clicking Delivered for every eligible slot)
- Customers (wallet charge + delivery notice)
- Platform ops (cron persistence across `git pull` / CI deploy)

## Goals / Non-Goals

**Goals:**

- Automate lunch (15:00) and dinner (23:00) mark-delivered for eligible slots using **one** shared service path.
- Eligibility = live parent + `service_date` + `meal_period` + `status=scheduled` (i.e. customer did not meal-off / admin did not skip).
- Per-slot failure isolation (wallet insufficient, missing price, frozen wallet) with structured logging and continue.
- Idempotent managed crontab install that survives deploy without YAML changes.
- Customer push when delivery becomes `delivered` (best-effort; never roll back charge/status).

**Non-Goals:**

- Changing meal-off deadline defaults to 03:00 (use `MealOffSettings` / admin settings if ops need that).
- Changing admin mark API contract or requiring frontend changes for MVP.
- Auto-skip, rider logistics (`delivery.DeliveryAssignment`), or kitchen demand confirmation coupling.
- Editing `.github/workflows/deploy.yml`.
- Distinguishing cron vs admin in UI (optional follow-up: expose `marked_by` / note).

## Decisions

### D1 — Reuse `mark_delivery`, do not reimplement charge/status

- **Choice:** Batch orchestrator loads eligible PKs, then calls `mark_delivery(delivery, 'delivered', marked_by=None, note='Auto-delivered by cron')` per slot.
- **Why:** Wallet idempotency, locks, Onahar, order completion already correct; matches admin click semantics.
- **Alternatives:** Call `charge_delivered_meal` alone → status drift; raw queryset `update(status=...)` → silent unpaid deliveries.

### D2 — Eligibility query mirrors kitchen “still expected” set

- **Choice:** Filter `OrderDelivery` with `service_date`, `meal_period`, `status=SCHEDULED`, and `live_delivery_q(service_date)` from `subscription_parent` (same live-parent idea as meal demand / today-board).
- **Why:** Meal-off users are already `skipped`; cancelled/expired parents excluded; no second meal-off deadline check at cron time (deadline only gates customer meal-off API; by 15:00/23:00 windows are past under defaults).
- **Alternatives:** Re-check `can_meal_off` at cron → wrong (would treat post-deadline scheduled meals as ineligible).

### D3 — Management commands + thin service

- **Choice:**
  - Service: `orders.services.auto_meal_delivery.run_auto_delivery(*, service_date, meal_period, dry_run=False) -> RunResult`
  - Commands: `auto_deliver_meals --meal-period lunch|dinner [--date YYYY-MM-DD] [--dry-run]` (one command with period flag preferred over two near-duplicates)
- **Why:** Testable without crontab; ops can backfill/dry-run; cron lines stay thin wrappers around `manage.py`.
- **Alternatives:** Celery beat → new infra not present; Django-Q → same.

### D4 — Cron times and timezone

- **Choice:** Crontab in `Asia/Dhaka`:
  - Lunch: `0 15 * * *` → `--meal-period lunch`
  - Dinner: `0 23 * * *` → `--meal-period dinner`
- `service_date` = business “today” via meal-off timezone (`meal_off_business_now().date()` or equivalent), not UTC calendar date alone.
- **Why:** Matches product schedule; aligns with existing meal-off TZ singleton.

### D5 — Failure isolation and locking

- **Choice:** Each slot in its own try/except around `mark_delivery` (already `@transaction.atomic` per call). Aggregate counts: attempted / delivered / skipped_idempotent / failed(+code). Process-level lock file (e.g. `flock` in cron wrapper or file lock in command) to prevent overlapping runs.
- **Why:** One empty wallet must not abort the whole lunch batch; admin can still manually retry failed `scheduled` rows.

### D6 — Notifications after successful deliver

- **Choice:** New helper `notify_meal_delivered(delivery)` using existing FCM (`send_to_tokens` / device tokens for customer user). Invoke from `mark_delivery` **after** successful commit path for `delivered` (or immediately after charge success inside the function, with try/except so FCM never rolls back the transaction — prefer: call **after** the atomic block returns, from a thin wrapper used by both API and cron, **or** best-effort inside `mark_delivery` outside the failure-sensitive charge path).
- **Preferred shape:** Keep `mark_delivery` atomic for money/status; add `mark_delivery_and_notify(...)` used by admin views + cron, OR call notify in views + cron after `mark_delivery` returns. Cron and admin **must both** call the same notify helper.
- **Why:** Product asks for notification; current mark path has none; dual call sites without a shared helper will drift.
- **Alternatives:** Cron-only notify → manual Delivered stays silent (product inconsistency).

### D7 — Managed cron installer (no YAML change)

- **Choice:** Add:
  - `scripts/cron/jobs/*.cron` or a single manifest listing schedule + command
  - `scripts/cron/install_managed_cron.sh` — activates venv, resolves `PROJECT_DIR` / `manage.py`, installs tagged crontab block (e.g. `# BEGIN BEFOOD-MANAGED` … `# END BEFOOD-MANAGED`), idempotent replace
  - `scripts/cron/run_auto_deliver.sh lunch|dinner` — `cd`, `source venv`, `python manage.py auto_deliver_meals ...`, log to `logs/cron-auto-deliver-*.log`
- Deploy already invokes installer; first deploy after merge installs jobs; subsequent pulls refresh the managed block.
- **Why:** Matches prior erp-backend pattern and existing deploy hook without touching CI YAML.

### D8 — Frontend scope

- **Choice:** No FE code in this change. Auto-delivered slots appear as `delivered` + wallet charged on next detail fetch; Delivered button hides when not `scheduled`.
- **Why:** Automation is server-side; page already consumes mark response semantics.

### D9 — System actor / audit

- **Choice:** `marked_by=None`, `note` contains stable auto-delivery marker (e.g. `Auto-delivered by cron (lunch)`). Do not invent fake admin users.
- **Why:** Schema already allows null `marked_by`; avoids phantom users.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Insufficient wallet leaves meals undelivered at 15:00/23:00 | Same as manual 422; log `WALLET_INSUFFICIENT_FOR_MEAL`; ops top-up + re-run command or admin mark |
| Missing published slot price blocks charge | Log `MEAL_SLOT_PRICE_MISSING`; ensure menu publish before cron |
| Cron TZ vs UTC server | Explicit `CRON_TZ=Asia/Dhaka` in crontab or schedule via installer using Dhaka; compute `service_date` in business TZ inside command |
| Double run / deploy overlap | `flock` + `mark_delivery` idempotency key |
| Notification failure alarms ops | Best-effort only; log and continue; status/wallet already committed |
| Product assumes “off by 3 AM” | Document real `MealOffSettings`; optionally ops sets lunch deadline to 03:00 via admin settings API — out of code hardcode |
| Deploy host without crontab permission | Installer fails loudly in deploy logs; document server requirement |

## Migration Plan

1. Ship service + command + tests (feature flag optional: settings `AUTO_MEAL_DELIVERY_ENABLED` default True in prod, False in tests).
2. Ship `scripts/cron/*`; do **not** change deploy YAML.
3. Deploy / pull → existing step runs installer → crontab updated.
4. Smoke: `--dry-run` for today’s lunch; then one real run in staging.
5. Rollback: installer can remove managed block, or crontab comment-out; code path unused if cron removed; no schema migration required for MVP.

## Open Questions

- Should notification also fire for **manual** admin Delivered? (**Recommendation: yes**, same helper.)
- Exact FCM copy / `data` deep-link (subscription vs order screen) — confirm with product; implement with sensible English/Bangla defaults if unset.
- Whether historical one-off packages (`Order`-backed slots) are included (yes via `live_delivery_q`) or subscription-only — **include both** unless ops says otherwise.
