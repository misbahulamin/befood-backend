## Context

BeFood already has month-scoped **meal cycle costing**:

```
MealCycle (year+month → total_meals = days × 2)
  └── MealCyclePlan (per MealCategory, draft|finalized)
        └── MealCyclePlanLine (ingredient + servings_count)
```

That answers “how many times is Chicken served this month?” It does **not** answer “on which dates / lunch vs dinner?” Cooks need a day calendar; customers with an active order need a gated **today’s menu**; owners with multiple packages (Regular, Student, …) need those calendars to stay **cooking-aligned** when quotas differ.

Stakeholders: verified admins (plan + kitchen), customers with purchased packages, backend team, future admin UI.

Constraints:

- Reuse `IsVerifiedAdmin` for admin schedule APIs; customer auth for today-menu.
- Keep cycle finalize math unchanged; schedule consumes finalized quotas as hard caps.
- Prefer service-layer business rules (`meals/services/`), thin DRF views.
- No `/api/v1` prefix — follow existing `/meals/` and `/orders/` mounts.
- Language/docs for API artifacts in English; chat language follows user preference.

## Goals / Non-Goals

**Goals:**

- One monthly menu schedule per finalized cycle plan (package × month).
- Assign ingredients to `(date, lunch|dinner)` slots with hard quota enforcement from plan lines.
- Publish lifecycle so kitchen can prep from full month while customers only see revealed “today” periods.
- Cross-package sync suggestions + explicit apply, respecting unequal quotas and lunch/dinner balance.
- Admin-configurable reveal clocks (default 08:00 / 16:00) in a business timezone.
- Customer today-menu API scoped to active orders covering today.
- Backend technical documentation after implementation.

**Non-Goals:**

- Changing how cycle `servings_count` or finalize costing works (except reopen guardrails).
- Inventory, purchasing, or stock deduction from schedule.
- Public browsing of tomorrow/future menus.
- Fully automatic silent sync that overwrites all packages without admin confirmation.
- Multi-outlet / multi-timezone kitchens in v1 (single business timezone setting).
- AI menu generation.

## Decisions

### 1. Domain model: Schedule → Slots → Items

```
MealCyclePlan (finalized)
        │ 1:1
        ▼
MonthlyMenuSchedule
  status: draft | published
  notes
        │ 1:N
        ▼
MonthlyMenuSlot
  service_date
  meal_period: lunch | dinner
  unique (schedule, service_date, meal_period)
        │ 1:N
        ▼
MonthlyMenuSlotItem
  ingredient FK
  unique (slot, ingredient)
```

**Why:** Mirrors the operational calendar (60/62 slots) while keeping assignments queryable and syncable. Separating slot vs item allows one main + multiple sides per meal without flattening into a single JSON blob.

**Slot generation:** On schedule create, optionally materialize all `cycle_days × 2` empty slots, or create slots lazily on first write. Prefer **lazy create on assign** plus a computed calendar view so empty months stay light; publish validation iterates the expected date×period set from the cycle calendar.

**Alternative considered:** Store only a flat list of `(date, period, ingredient_id)` without slot entity. Rejected — uniqueness and “one main per slot” are harder; sync joins get messier.

**Alternative considered:** Shared cycle-level “cooking board” as source of truth with package overlays. Attractive for sync, but unequal quotas (12 vs 10 chicken) force overlays anyway. Keep **per-package schedules** as source of truth; sync is a service over them.

### 2. Quota engine (hard rules)

Service: `meals/services/menu_schedule.py`

| Rule | Enforcement |
| --- | --- |
| Ingredient must be on linked plan | On every assign / bulk save |
| `count(assignments of ingredient) ≤ plan_line.servings_count` | On every assign / bulk save / apply-sync |
| ≤ 1 ingredient with `product_role=main` per slot | On assign |
| On **publish**: every date×period in month has exactly 1 main | Publish gate |
| Non-mains: quota cap only; under-fill allowed on publish | Soft |

Bulk `PUT .../assignments/` replaces the month matrix in one transaction (Excel/calendar UX), returning per-ingredient `{planned, used, remaining, lunch_count, dinner_count}`.

### 3. Lifecycle vs cycle plan reopen

```
finalized plan ──create──▶ schedule draft ──publish──▶ published
                              ▲                │
                              └── unpublish ───┘
```

- **Reopen published plan:** blocked while schedule `published`.
- **Reopen with draft schedule:** **delete the schedule** (or clear all assignments and delete schedule row) inside the same transaction as reopen — simplest integrity story; admin rebuilds schedule after re-finalize.
- Changing plan lines after reopen can invalidate quotas; deleting draft schedule avoids orphan over-quota calendars.

**Alternative:** Soft-invalidate schedule and keep history. Deferred — no audit product requirement yet.

### 4. Cross-package sync algorithm

Service: `meals/services/menu_sync.py`

**Inputs:** `source_schedule_id` (primary kitchen template, usually highest-volume package), `target_schedule_ids[]` or “all other schedules in cycle”.

**Phases:**

1. **Mirror mains where possible**  
   For each source slot with a main `I`, if target plan has remaining quota for `I` and target slot has no main yet → propose `I`.

2. **Fill remaining target mains**  
   For empty target slots, place remaining main quotas using **balance heuristic**:
   - For each ingredient with remaining `R`, recommended split: `lunch = ceil(R/2)`, `dinner = floor(R/2)` (odd remainder → lunch), then greedily fill empty slots preferring that period’s deficit.
   - Prefer ingredients that maximize future overlap with other packages’ already-filled slots when multiple choices exist (score = how many sibling schedules already use this ingredient on this slot).

3. **Mirror sides/staples** similarly with remaining quotas (lower priority than mains).

4. **Divergence report**  
   For each date×period, list packages whose main differs → warnings for admin UI.

**Apply:** explicit `POST .../apply-sync/` with the suggestion payload (or server recompute + apply with same params). Never auto-apply on source edit in v1 (prevents surprising overwrites); optional later “watch mode”.

**Why not force identical menus?** Quotas differ; forced identity is impossible. Best-effort overlap + clear remaining manual slots is the robust ops model.

### 5. Reveal settings

Singleton (or single-row) `MenuRevealSettings`:

- `timezone` (default `Asia/Dhaka` — adjust if project already has a canonical TZ)
- `lunch_reveal_time` (TimeField, default 08:00)
- `dinner_reveal_time` (TimeField, default 16:00)

Admin GET/PATCH under `/meals/menu-reveal-settings/`.

Customer visibility for local date `D`:

- Include lunch if `now_local ≥ D + lunch_reveal` and schedule published with lunch items.
- Include dinner if `now_local ≥ D + dinner_reveal` and dinner items exist.
- Before lunch reveal: return package eligibility but empty periods (or explicit `lunch_available_at`).

### 6. Customer today-menu eligibility

Service uses `orders.Order`:

- Auth: verified customer token (same pattern as order APIs).
- Eligible meals: orders where `customer` matches, `order_status != cancelled`, `order_start_date ≤ today_local ≤ order_end_date`.
- Join to published `MonthlyMenuSchedule` for `(cycle year/month of today, meal_category=order.meal)`.
- Endpoint: `GET /meals/today-menu/` (customer), lean serializer.

**Do not** use public `AllowAny`. Full month remains admin-only.

### 7. API shape (resource nouns)

| Area | Endpoints |
| --- | --- |
| Schedules | `GET/POST /meals/menu-schedules/`, `GET/PATCH /meals/menu-schedules/{id}/` |
| Assignments | `PUT /meals/menu-schedules/{id}/assignments/` (bulk), optional slot item CRUD |
| Lifecycle | `POST .../publish/`, `POST .../unpublish/`, `GET .../quota-summary/` |
| Sync | `POST /meals/menu-schedules/{id}/sync-suggestions/`, `POST .../apply-sync/` |
| Reveal | `GET/PATCH /meals/menu-reveal-settings/` |
| Customer | `GET /meals/today-menu/` |

Filter schedules by `cycle`, `meal_category`, `status`. Swagger tags: **Admin Meal Menu Schedule**, **Customer Today Menu**.

### 8. Permissions

| Caller | Full month schedule | Reveal settings | Today menu |
| --- | --- | --- | --- |
| Verified admin | Yes | Yes | Optional (debug) |
| Customer (active order) | No | No | Yes (own packages) |
| Anonymous | No | No | No |

### 9. Documentation

After APIs land, write `meals/docs/backend/monthly-meal-menu-schedule.md`: mental model linking cycle plan → schedule, quota rules, sync workflow, reveal clocks, today-menu eligibility, full call order, examples, errors, verification checklist. Cross-link from meal-cycle-management.md.

## Risks / Trade-offs

- **[Risk] Unequal quotas leave unavoidable divergence** → Mitigation: suggestion engine + divergence warnings; never claim perfect sync.
- **[Risk] Admin edits source after targets synced** → Mitigation: no silent auto-sync in v1; re-run suggestions explicitly.
- **[Risk] Reopen deletes draft schedule work** → Mitigation: block reopen when published; warn in API detail when draft schedule will be deleted; document clearly.
- **[Risk] Timezone bugs around midnight / DST** → Mitigation: store explicit IANA TZ; tests around reveal boundaries; Bangladesh has no DST but keep zone-aware code.
- **[Risk] Large bulk payloads (31×2×N items)** → Mitigation: single transactional bulk endpoint; validate in service before write; keep mobile today-menu lean.
- **[Trade-off] Materialize all slots vs lazy** → Lazy writes + virtual calendar validation chosen for simplicity.

## Migration Plan

1. Add models + migration (no data backfill required).
2. Ship admin APIs + services + tests.
3. Ship reveal settings + customer today-menu.
4. Document; seed optional demo schedule in tests only.
5. Rollback: reverse migration drops new tables; cycle APIs unaffected. Feature-flag unnecessary if endpoints are additive.

## Open Questions

- Confirm business timezone default (`Asia/Dhaka` vs project `TIME_ZONE`).
- Whether today-menu should return **both** lunch and dinner after dinner reveal, or only the “current” period — **decision in this design: both after their respective reveals on that calendar day** (matches “after 4pm dinner becomes available” without hiding lunch).
- Whether non-main items appear on customer today-menu — **yes**, all slot items for the visible period.
- Exact customer permission class name already used by orders (`IsVerifiedCustomer`) — implementers must match existing auth, not invent a parallel one.
