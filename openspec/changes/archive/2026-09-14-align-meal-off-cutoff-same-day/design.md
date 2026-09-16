## Context

Customer meal-off/on already exists (`orders/services/meal_off.py`) with a singleton `MealOffSettings` and admin GET/PATCH. Eligibility, mutations, and `meal_off_deadline_at` all call `meal_off_deadline(service_date, meal_period)`.

Current backend math:

- Lunch on `D` → `(D − 1) + lunch_off_time` (default `23:59`)
- Dinner on `D` → `D + dinner_off_time` (default `14:00`)
- Inclusive compare: allow while `business_now <= deadline`

Product / Admin Panel intent (frontend already aligned):

- Lunch on `D` locks once business time passes midnight on `D` (example: after `00:01` on `D`)
- Dinner on `D` locks once business time passes afternoon cut-off on `D` (example: after `16:01` on `D`)
- Defaults and admin-updated times must drive the same backend helper used by Off, On, payloads, and kitchen demand confirmation

Stakeholders: customers (mobile/web), verified admins (settings), kitchen/demand consumers of the same deadline.

## Goals / Non-Goals

**Goals:**

- Make lunch and dinner cut-offs both **same-day** on the service date: `D + lunch_off_time` / `D + dinner_off_time`.
- Ship product defaults: lunch `00:00:00`, dinner `16:00:00`, timezone `Asia/Dhaka`.
- Preserve one shared deadline for meal-off and meal-on.
- Keep admin settings API shape (`timezone`, `lunch_off_time`, `dinner_off_time`); only semantics/defaults change.
- Migrate model defaults and the singleton when it still holds legacy defaults; leave intentional custom times in place (calendar-day semantics still change for lunch).
- Update tests, OpenAPI blurbs, and backend/frontend docs to match.

**Non-Goals:**

- Separate Off vs On deadlines.
- Per-package or per-customer cut-offs.
- Changing wallet / skip / reopen meal-on business rules.
- Frontend Admin Panel rewrite (assumed already correct).
- Changing kitchen “default period” heuristic formula (still: before `dinner_off_time` → lunch, else dinner); only the clock value default shifts to `16:00`.

## Decisions

### 1. Same-day deadline for both periods

```text
lunch  on D → datetime.combine(D, lunch_off_time, tz)
dinner on D → datetime.combine(D, dinner_off_time, tz)
```

**Why:** Matches product examples and frontend. Removes the special-case `timedelta(days=1)` for lunch that caused FE/BE drift.

**Alternatives considered:** Keep `D−1` and only change defaults to encode “midnight” as previous-day `23:59` — rejected; admin UX and docs already treat cut-off as a clock on the meal day, and product examples use date `D` midnight / `D` 4 PM.

### 2. Defaults `00:00` / `16:00` with inclusive `<=`

Keep existing inclusive semantics: at exactly the configured time, Off/On still allowed; one second later, rejected. Product phrasing “after 12:01 AM / 4:01 PM” is satisfied by defaults `00:00` / `16:00` (blocked by `00:00:01` / `16:00:01`). Admins who want a later lunch cut-off set a later `lunch_off_time` (e.g. `08:00`).

**Why:** Minimal code change; no new “exclusive after minute” rule.

**Alternatives:** Default lunch `00:01` literally — rejected as noisier; `00:00` is the clear midnight cut-off.

### 3. Single helper remains source of truth

Do not duplicate calendar math in views, serializers, or meal-demand. Only change `meal_off_deadline`; demand confirmation already calls it.

**Why:** Guarantees FE payloads (`meal_off_deadline_at`, `can_meal_*`) and kitchen `confirmation_status` stay consistent with mutations.

### 4. Settings migration policy

Data migration on deploy:

1. Alter field defaults to `00:00` / `16:00` and update help text (“on the lunch/dinner service date”).
2. If singleton `pk=1` exists with **exact** legacy pair `(23:59, 14:00)`, update to `(00:00, 16:00)`.
3. If either time was customized, leave values as-is but document that lunch now applies on **service date** (ops must re-check Admin Panel).

**Why:** Avoid silently rewriting intentional custom clocks; still fix environments that never left the old product defaults.

**Alternatives:** Always overwrite to new defaults — rejected (destroys admin customization). Never migrate row — rejected (prod keeps wrong product defaults until someone remembers to PATCH).

### 5. Docs and API descriptions

Update customer-meal-off docs, OpenAPI operation descriptions mentioning “previous day 23:59 / same day 14:00”, and meal-demand docs that cite prior-day lunch. No new endpoints.

## Risks / Trade-offs

- **[Risk] Breaking change for lunch windows** — Customers who could Off lunch until late evening of `D−1` under old math may gain or lose hours depending on configured `lunch_off_time`. → Mitigation: release note + admin verify settings after deploy; frontend already expected same-day midnight.
- **[Risk] Custom `lunch_off_time` kept but day shifts** — e.g. admin had `22:00` meaning “night before”; after change it means 22:00 on meal day. → Mitigation: migration notes; call out in Admin Panel / ops checklist.
- **[Risk] Kitchen default period flips at 16:00 instead of 14:00** — Afternoon lunch default window lengthens by two hours under new dinner default. → Mitigation: intentional with product dinner cut-off; admin can set dinner time independently.
- **[Trade-off] Inclusive exact-second allow** — At `16:00:00.000` still allowed; product copy says “after 4:01”. Acceptable; document.

## Migration Plan

1. Land code: `meal_off_deadline` same-day lunch + model defaults/help text.
2. Run schema + data migration (defaults + conditional singleton update).
3. Deploy; smoke-test admin GET settings, customer lunch/dinner Off/On around boundaries, demand `confirmation_status`.
4. Ops: open Admin meal-off settings, confirm lunch `00:00` / dinner `16:00` (or intended custom), save if needed.
5. Rollback: revert commit/migration; if data migration updated the singleton, reverse migration restores `(23:59, 14:00)` only when current values are `(00:00, 16:00)`.

## Open Questions

- None blocking implementation. If product later wants lunch cut-off later in the morning of `D`, admin PATCH `lunch_off_time` without further code changes.
