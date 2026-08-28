## Context

BeFood production already runs subscription meals from `MealCategory` packages (seeded as Student / Regular / **Premium** — there is no separate Corporate model). Monthly cook plans flow through `MealCycle` → `MealCyclePlan` → `MonthlyMenuSchedule` → `MonthlyMenuSlot` (one row per `service_date` × `lunch|dinner`). Publish locks subscription selling prices on the slot (`ingredient_cost_snapshot`, `operational_cost_snapshot`, `profit_snapshot`, `final_meal_price_snapshot`) using plan `profit_percent`.

Instant Meal must let non-subscribers browse the **same published cook-day meals** as display cards, with a **separate** admin Instant profit margin and a **display window** (Today / 3 / 7 / 15 / 25 / 30 days). Order placement is out of scope. Existing subscription calculation and APIs must not break.

A draft singleton `InstantMealSettings` already exists in `meals/models.py` (profit + duration) but has no migration/API yet. Settings patterns to mirror: `MenuRevealSettings`, `MealOffSettings`, `OrderWalletSettings`.

## Goals / Non-Goals

**Goals:**

- Verified-admin Instant settings: `profit_percent` (default `50.00`) and `duration_days` ∈ `{1, 3, 7, 15, 25, 30}`.
- Public Instant Meal list API projecting published slots into one card per package × date × meal period.
- Instant price = ingredient cost + month per-meal operational cost + Instant profit on ingredient cost (same arithmetic shape as slot preview, different profit source).
- Past dates excluded; window is inclusive from local “today” for `duration_days` calendar days.
- Frontend + backend docs so clients can integrate display without Instant order APIs.

**Non-Goals:**

- Instant Meal checkout, wallet debit, delivery, or inventory reservation.
- Changing `calculate_package_totals`, `finalize_plan`, `publish_schedule`, slot snapshot writes, or subscriber wallet charge rules.
- New duplicate menu/package/slot tables.
- Rewriting search indexing for `instant_meal` (optional follow-up after API is stable).
- Renaming Premium → Corporate.

## Decisions

### 1. Configuration: isolated singleton `InstantMealSettings`

- **Choice:** Keep/finish `InstantMealSettings` (`pk=1`, `load()`, non-deletable) with `profit_percent` and `duration_days`. Admin `GET|PATCH` under `meals/` (e.g. `/meals/instant-meal-settings/`), `IsVerifiedAdmin`, same shape as `MenuRevealSettingsView`.
- **Alternatives:** Stuff fields into `MenuRevealSettings` (rejected — different concern); env-only config (rejected — admin must change without deploy).
- **Validation:** Reject `duration_days` outside the allowlist with `422`; clamp/validate `profit_percent` ≥ 0 (existing model validators).

### 2. No InstantMeal persistence table

- **Choice:** Instant Meals are **read-time projections** of published `MonthlyMenuSlot` rows. No new meal entity table for v1.
- **Stable card id:** Deterministic string `public_id` = `{meal_category.public_id}:{service_date}:{meal_period}` (no slot UUID migration). Document as opaque id for frontend keys.
- **Alternatives:** Persist `InstantMeal` rows on publish (rejected — sync/unpublish complexity, duplicate source of truth); add `public_id` on `MonthlyMenuSlot` (deferred — extra production migration).

### 3. Source filter: published schedules only, all packages with published menus

- **Choice:** Query slots where `schedule.status == published`, `service_date` in `[today, today + duration_days - 1]` (business local date; reuse project localdate / `Asia/Dhaka` consistency with menu services), slot has ingredients (assigned). Include every package that has a published schedule in range (Student, Regular, Premium, future categories).
- **Draft / unpublished** schedules and empty slots are omitted.
- Cross-month windows are allowed (e.g. late-month 7-day window spans next month’s published cycle).

### 4. Pricing: reuse helpers, never write subscription snapshots

- **Formula (Instant):**
  ```text
  ingredient_cost = slot.ingredient_cost_snapshot
                    (fallback: sum combined_unit_cost_per_customer for slot ingredients)
  operational_cost = resolve_per_meal_operational_cost(service_date.year, service_date.month)
                    (prefer live month op-cost; snapshot may be used only if resolve fails and snapshot exists — prefer fail closed / omit card if neither available)
  profit           = ingredient_cost × InstantMealSettings.profit_percent / 100
  price            = ingredient_cost + operational_cost + profit
  ```
- **Choice:** New service module e.g. `meals/services/instant_meals.py` that calls existing `build_one_meal_price_preview` / cost helpers with Instant `profit_percent`. Prefer published `ingredient_cost_snapshot` when present so Instant cost matches the cook menu lock; always apply Instant profit (not plan profit).
- **Must not:** Call `snapshot_prices_for_schedule`, mutate slot snapshots, or change `MealCyclePlan.profit_percent`.
- **Subscriber marketing value:** `subscriber_price` = `final_meal_price_snapshot` when present; otherwise omit/null. Backend does **not** return marketing copy; frontend builds static Bangla/English text from `subscriber_price`.

### 5. Card payload shape

| Field | Source |
|-------|--------|
| `public_id` | Composite id above |
| `name` | Joined ingredient display names for the slot (stable order: product_role then name) |
| `meal_type` / `meal_period` | `lunch` \| `dinner` (API exposes consistent snake_case enum; docs map Lunch/Dinner labels) |
| `date` / `service_date` | Slot `service_date` (ISO date) |
| `package_source` / `package_public_id` | `MealCategory.public_id` |
| `package_name` | `MealCategory.meal_name` |
| `price` | Instant computed price |
| `ingredient_cost` | Cost used in Instant formula |
| `operational_cost` | Per-meal op cost used |
| `profit_percent` | Instant settings value used |
| `image` | Optional URL from `MealCategory.meal_thumbnail` (no per-slot image today) |
| `subscriber_price` | Slot `final_meal_price_snapshot` or null |
| `ingredients` | Optional lean list `{name, product_role}` for card detail — include if cheap; keep mobile-friendly |

Omit inventing `subscription_message` string on the API; document frontend static template instead.

### 6. Ordering and API surface

- **Order:** Ascending `service_date`, then `meal_period` (`lunch` before `dinner`), then `package_name` / package id for stability.
- **Endpoint:** `GET /meals/instant-meals/` (AllowAny or same as `public-package-menu`), paginated if large; default page size aligned with project list defaults.
- **Admin:** `GET|PATCH /meals/instant-meal-settings/`.
- Optional filter query later (`package_public_id`, `meal_period`) — include if cheap in v1; not required for MVP if list is small.

### 7. Documentation

- Backend: `meals/docs/backend/instant-meal-offering.md`
- Frontend: `meals/docs/frontend/instant-meal-offering.md` (admin settings + public list, field meanings, call order, no order API)

## Risks / Trade-offs

- **[Risk] Live Instant price drifts from published ingredient snapshot if catalog costs change while schedule stays published** → Prefer `ingredient_cost_snapshot` for Instant ingredient cost so display stays aligned with published cook menu; document that Instant **profit** still follows Instant settings (so Instant `price` can differ from `subscriber_price` even when ingredient base matches).
- **[Risk] Missing operational cost month blocks Instant pricing** → Same as publish path: omit or return structured error for unpriceable slots; do not invent `0` silently.
- **[Risk] Composite `public_id` is not a DB UUID** → Document clearly; introduce real UUID entity only if Instant orders are added later.
- **[Risk] Large windows (30 days × packages × 2 periods) grow payload** → Paginate; keep fields lean for mobile.
- **[Trade-off] No Instant order yet** → Frontend can show cards and CTA stub only; avoids premature payment/inventory coupling.
- **[Trade-off] Premium vs user “Corporate” naming** → Specs use actual `MealCategory.meal_name`; no rename.

## Migration Plan

1. Add migration for `InstantMealSettings` if not already applied (single row bootstrap via `load()` / `get_or_create(pk=1)`).
2. Ship admin settings API + Instant list service/API + tests + docs.
3. Deploy: additive only; no data backfill of menus required.
4. **Rollback:** Remove routes/views; settings table can remain harmless. Do not reverse subscription-related migrations.

## Open Questions

- Whether Instant list should honor `MenuRevealSettings` for **today’s** lunch/dinner visibility, or show today’s meals as soon as the calendar day starts. **Default decision for this change:** Instant list uses **calendar date window only** (no reveal-time gate), so marketing can show the full day’s Instant cards; reveal gating remains for subscriber today-menu. Revisit if product wants Instant to match kitchen reveal.
- Whether to index Instant projections into `SearchDocument` in this change. **Default:** out of scope; leave search type reserved.
