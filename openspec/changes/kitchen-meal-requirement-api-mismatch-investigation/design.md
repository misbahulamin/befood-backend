## Context

Production admins observe that kitchen totals for “today” can rise during the day (example: 21 → 22 after ~11:00–12:00 Asia/Dhaka) on:

- `GET /orders/kitchen/today-meal-requirement/`
- `GET /orders/kitchen/today-order-details/`

(and the `/api/v1/web/orders/...` aliases).

This design is the **code-backed investigation report**. No runtime code is changed in this OpenSpec change. A follow-up apply MUST implement only the production-safe fix selected below.

### Current Flow

```text
HTTP GET /orders/kitchen/today-meal-requirement/
  |  (also web_urls alias → same view)
  v
KitchenTodayMealRequirementView  (orders/api/views.py)
  |  permission: IsVerifiedAdmin
  |  _resolve_kitchen_today_slot(request)
  |    → MealOffSettings timezone + dinner_off_time
  |    → default: today + lunch if now < dinner_off_time else dinner
  |    → optional query: service_date, meal_period, package_public_id
  v
build_kitchen_requirement()  (orders/services/meal_demand.py)
  |
  +--> get_demand() / _demand_queryset()
  |      OrderDelivery filter(service_date, meal_period)
  |      + live_delivery_q(service_date)   # active/cancelled-serving parents
  |      - exclude meal_service_blocked_low_balance
  |      aggregates: expected, meal_off(skipped), distinct customers
  |
  +--> get_ingredient_requirements()  # scales by final_cooking_count
  v
KitchenTodayRequirementSerializer (response shape only)
  |
  Models: OrderDelivery (+ CustomerSubscription | Order → MealCategory / CustomerProfile)

HTTP GET /orders/kitchen/today-order-details/
  v
KitchenTodayOrderDetailsView
  → same _resolve_kitchen_today_slot
  → build_kitchen_order_details()
       same _demand_queryset
       .exclude(status=skipped)
       per-row published menu labels
  → KitchenTodayOrderDetailsSerializer
```

**Important:** Kitchen “today” endpoints are **live queryset calculations**. They do **not** read `MealDemandSnapshot`. Snapshots are only for `GET .../meal-history/` via `confirm_meal_demand_snapshots`.

### Status inclusion in kitchen math

| Status | In `_demand_queryset`? | In `expected_meal_count` / `total_customers`? | In `final_cooking_count`? | In order-details `customers[]` / `count`? |
|--------|------------------------|-----------------------------------------------|---------------------------|-------------------------------------------|
| `scheduled` | Yes (if live parent + not low-balance blocked) | Yes | Yes | Yes |
| `delivered` | Yes | Yes | Yes | Yes |
| `skipped` | Yes | Yes (expected + customers) | No (`expected − meal_off`) | No |
| `pending` / delivery `cancelled` | N/A — delivery statuses are only scheduled / delivered / skipped | — | — | — |

### Mid-day mutation paths that can change the same-slot count

1. **`subscribe_customer` → `ensure_subscription_deliveries`**  
   Creates today’s missing slots. If meal-off cutoff has **not** passed → `scheduled` (increases final cook count). If past cutoff → `skipped` with `note=cutoff_passed` (increases expected/total_customers, not final).
2. **Customer `GET .../subscriptions/current/` / `orders/current-package`** also calls `ensure_subscription_deliveries` (backfill missing horizon slots).
3. **Menu publish** (`publish_schedule`) calls `ensure_all_active_subscription_deliveries()` — can create many missing rows mid-day when a month becomes published.
4. **Customer meal-on** before cutoff restores `skipped` → `scheduled` → final count +1.
5. **Low-balance resume** (`meal_service_blocked_low_balance` cleared, e.g. after recharge approval) re-includes an existing scheduled/delivered row that was previously excluded → final count +1.
6. **Default slot switch** (no query params): at `dinner_off_time` (default **16:00** Asia/Dhaka) default period flips lunch → dinner. This can look like a “mismatch” if the admin UI does not pin `meal_period`. Default flip is **not** at 11:00/12:00 unless production `dinner_off_time` was configured near noon.

### Cron / cache / timezone findings

- **Managed cron** (`scripts/cron/install_managed_cron.sh`): lunch auto-deliver 15:00 BD, dinner 23:00 BD, wallet threshold 08:00/20:00 BD. **Does not** install `ensure_subscription_deliveries`. Auto-deliver only marks `scheduled` → `delivered` (counts unchanged). Wallet cron can **block** (counts decrease), not create deliveries.
- **HTTP/API cache:** none on these kitchen views. Redis used for Channels, not response caching. Only an in-request `menu_cache` dict for ingredient name resolution.
- **Timezone:** Django `TIME_ZONE = Asia/Dhaka`; kitchen “today” uses `meal_off_business_now()` = `timezone.now().astimezone(MealOffSettings.timezone)` (default Asia/Dhaka). Mid-morning → noon same BD calendar day is **unlikely** to be a UTC date-roll bug.
- **Duplicates:** unique constraints `(subscription, service_date, meal_period)` and `(order, service_date, meal_period)` — duplicate same-slot rows for one parent are blocked at DB level.

## Goals / Non-Goals

**Goals:**

- Freeze a code-backed root-cause narrative and evidence map.
- Rank likely production scenarios for 21 → 22 same-day drift.
- Recommend a production-safe fix that keeps deliveries, wallet charging, and history intact.
- Provide read-only SQL / operator checks to confirm the live cause on a concrete incident day.

**Non-Goals:**

- Shipping runtime code, migrations, or production data writes in this change.
- Changing wallet debit / auto-delivery charge logic.
- Deleting or rewriting historical `OrderDelivery` rows.
- Treating `MealDemandSnapshot` as the live kitchen source without an explicit product decision.

## Decisions

### 1. Root cause (primary)

**Choice:** Treat the observed rise as **expected behavior of a live kitchen queryset**, not a broken aggregate formula or server cache.

**Evidence:**

- `KitchenTodayMealRequirementView.get` / `KitchenTodayOrderDetailsView.get` always call `build_kitchen_*` with no cache layer.
- `_demand_queryset` reads current `OrderDelivery` rows every request.
- Frontend/backend docs already note mid-day drops when low-balance block applies (“refresh uses live data”).
- Slot creation paths (`subscribe_customer`, ensure on current, menu publish) can insert **today** rows while the kitchen page is open.

**Alternatives considered:**

- Cache/stale morning response → rejected (no endpoint cache).
- UTC vs Dhaka date flip at 11–12 → rejected for same BD morning/noon window.
- Auto-deliver cron creating extras → rejected (status transition only; unique constraints).

### 2. Most likely concrete drivers for +1 final cook count

Ranked for **same `service_date` + same `meal_period`**:

1. **Late same-day subscription before that period’s meal-off cutoff** creating `scheduled` (depends on production `lunch_off_time` / `dinner_off_time`).
2. **Low-balance unblock** re-including an already-scheduled delivery.
3. **Customer meal-on** before cutoff.
4. **Menu publish / ensure backfill** creating a previously missing today’s `scheduled` slot.
5. **UI comparing different periods** (default lunch → dinner at `dinner_off_time`, or missing pinned filters) — strong confounder when params are omitted; default switch time is dinner_off (typically 16:00), so 11–12 reports need explicit `meal_period` confirmation.

If production `lunch_off_time` is still **00:00**, a subscribe after midnight creates **skipped** lunch → `final_cooking_count` should **not** rise for lunch from subscribe alone; then prefer (2)/(3)/(4) or a mis-pinned period.

### 3. Recommended production-safe fix (follow-up implementation)

**Choice (preferred):** Keep live deliveries and wallet logic unchanged. Add a **kitchen cook freeze gate** at meal-off cutoff for kitchen APIs only:

- Before cutoff: live calculation (current behavior) — kitchen can still react to meal-off / meal-on.
- At/after cutoff for that `(service_date, meal_period)`: kitchen requirement + order-details MUST use a **frozen eligibility snapshot** (or equivalent: exclude deliveries whose `created_at` is after cutoff **and** were never meal-on eligible before cutoff — product to confirm exact rule).

Pragmatic v1 freeze rule (recommended):

- After meal-off deadline for slot S, kitchen counts include only deliveries that existed as cook-eligible (`scheduled`/`delivered`, not low-balance blocked) **at or before** the deadline; new post-cutoff `scheduled` rows (late subscribe after cutoff already become `skipped` today) and post-cutoff low-balance resumes MAY be excluded from kitchen cook lists **without** deleting deliveries or changing auto-deliver/wallet (billing can still charge if product wants — or keep auto-deliver aligned with freeze; **product must choose**).

**Safer minimal fix (lower risk, partial):**

- Admin SPA **must always send explicit `service_date` + `meal_period`** for kitchen pages and PDFs (eliminates default period flip confusion).
- Ops runbook: after cutoff, treat kitchen number as advisory if live; rely on `confirm_meal_demand_snapshots` for audit.
- Optionally surface `confirmation_status` + “live / may change until cutoff” banner (already partially present via `confirmation_status`).

**Alternatives rejected for first fix:**

- Serving only `MealDemandSnapshot` all day → wrong before cutoff (meal-off still moving).
- Stopping `ensure_subscription_deliveries` from creating today’s rows → breaks subscription continuity / billing eligibility.
- Hard-deleting mid-day rows → violates “no historical delete”.

### 4. Investigation completeness bar

**Choice:** Code analysis in this design is sufficient to declare primary root cause. Production read-only SQL (tasks) confirms which mutator fired on a given incident day before coding the freeze.

## Risks / Trade-offs

- **[Risk] Freeze kitchen but auto-deliver still charges late-unblocked customers** → Mitigation: align auto-deliver eligibility with kitchen freeze OR document intentional “cook N / bill N+1” and alert ops.
- **[Risk] Freezing too early undercounts meal-on before cutoff** → Mitigation: freeze only after meal-off deadline (same clock as meal-off settings).
- **[Risk] Admin UI without pinned period misattributes lunch vs dinner** → Mitigation: require query params in SPA; backend docs emphasize response `meal_period`.
- **[Risk] Operators misread `total_customers` / `expected_meal_count` (includes skipped) vs `final_cooking_count`** → Mitigation: train kitchen UI to key off `final_cooking_count` / order-details `count`.

## Migration Plan

1. Complete read-only production verification queries for one incident day (tasks §1).
2. Product picks freeze vs SPA-pin-only vs freeze+auto-deliver alignment.
3. Separate OpenSpec apply / change implements code + tests; no data migration required for SPA-pin; freeze may add snapshot write or cutoff filter only.
4. Rollback: revert kitchen filter/snapshot serve; deliveries and wallet ledgers untouched.

## Open Questions

1. On the reported day, did the admin SPA send explicit `meal_period`, and which response field was compared (final vs total_customers vs order-details count)?
2. Production `MealOffSettings.lunch_off_time` / `dinner_off_time` values?
3. Should post-cutoff low-balance resume still be cooked/charged the same day?
4. Should kitchen freeze reuse `MealDemandSnapshot` upserted at cutoff, or a dedicated kitchen freeze table?

## Investigation Report (operator summary)

### Root Cause

Kitchen APIs recalculate from live `OrderDelivery` querysets on every GET. Same-day inserts or re-inclusions (late subscribe before cutoff, ensure backfill, meal-on, low-balance resume) change the cook headcount. This is live data drift, not a cached stale total and not a UTC date bug for morning→noon Asia/Dhaka. Separately, omitting `meal_period` can switch the default slot at `dinner_off_time`, which must not be confused with same-slot drift.

### Impact

- **Kitchen cook quantity / PDFs:** Yes — live numbers can rise (or fall) mid-day; chefs may under/over prep if they print early and do not refresh, or if they cook from a morning PDF.
- **Display-only?** Partially — display reflects DB truth for “who is currently cook-eligible,” but product intent for kitchen may want a frozen cook list after cutoff.
- **Customer billing / wallet:** Existing auto-deliver + mark_delivery paths are separate; count drift does not by itself invent charges. Late `scheduled` slots can still be charged at auto-deliver time unless eligibility is aligned with a freeze.

### Evidence from Code

- Live builders: `orders/services/meal_demand.py` (`build_kitchen_requirement`, `build_kitchen_order_details`, `_demand_queryset`).
- Slot resolution: `resolve_default_kitchen_slot` / `_resolve_kitchen_today_slot` in `orders/api/views.py`.
- Slot creation: `ensure_subscription_deliveries` / `subscribe_customer` in `orders/services/subscription_service.py`; menu publish hook in `meals/services/menu_schedule.py`.
- Docs already admit live mid-day change: `orders/docs/frontend/meal-demand-kitchen-planning.md` (low-balance omit + refresh).

### Possible Data Scenario

Morning: 21 cook-eligible lunch rows. Before noon, one more customer becomes cook-eligible (new scheduled delivery or unblock/meal-on). Refresh → 22. Or morning response was lunch and later response was dinner without pinned filters (different universe of customers).

### Recommended Production Safe Fix

1. Short term: pin `service_date` + `meal_period` in Admin SPA; use `final_cooking_count` / order-details `count`; refresh after cutoff before final cook.
2. Medium term: after meal-off deadline, freeze kitchen eligibility for that slot without deleting deliveries or changing wallet charge math unless product explicitly aligns auto-deliver with the freeze.
3. Verify with read-only SQL: today’s deliveries with `created_at` after morning print time; low-balance flag flips; meal-on transitions.
