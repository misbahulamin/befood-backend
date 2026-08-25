## Context

### Current frontend state (`befood-frontend`)

Public monthly-package detail pages resolve package identity from `GET /meals/` and `GET /meals/{public_id}/` via slug matching (`mealNameToSlug`). However, `DetailMenuPlan` uses `buildPlaceholderMenuDays()` — rotating Bangla dish names with no API connection. Hero shows hardcoded "৩০/৩১ দিন". Publish status is not checked; a "Demo Menu · API-ready" badge is always shown.

Authenticated flows already exist:
- `GET /meals/my-package-menu/` — post-subscribe full month (requires active subscription)
- `GET /meals/order-menu-preview/` — pre-order preview (requires verified customer auth)

Neither is wired to `/monthly-package/:packageSlug`.

### Current backend state (`befood-backend`)

Admin workflow is complete: cycle plan → menu schedule → assignments → publish/unpublish. Customer reads filter `status=published` only via `published_schedule_for_meal()`. Response includes flat `days[]` with `service_date`, `meal_period`, `ingredients[]`, and `schedule_published` boolean.

**Gaps:**
1. No **public** (unauthenticated) endpoint for marketing pages
2. Menu responses lack `cycle_days`, `total_meals`, `meal_period` metadata
3. Frontend must group flat `days[]` by date for calendar/list views (acceptable; reuse `buildPlanDayRows` pattern from `monthlyMenuPlan.ts`)

### Stakeholders

- Prospective customers browsing `/monthly-package/*` (no login)
- Verified customers on order flow and `/account/monthly-menu` (existing paths)
- Meal ops admins (no workflow change)

## Goals / Non-Goals

**Goals:**

- Public marketing pages show **only published** monthly menus from the backend
- Calendar view and list view both consume the same API payload
- Dynamic "30 Days Menu" / "31 Days Menu" label from `cycle_days`
- Meal option (lunch / dinner / both) from `meal_period` on API response
- Unpublished months show a friendly empty state (no fake placeholder meals)
- Loading and error states on frontend menu section
- Additive metadata on existing authenticated menu endpoints for consistency

**Non-Goals:**

- Changing admin publish/finalize workflows
- CMS migration for static marketing copy (policies, FAQs, included items)
- Persona filter / compare table API integration
- Meal OFF / delivery actions on public pages
- Pre-grouped calendar JSON (frontend groups flat `days[]`; proven pattern exists)
- Making schedule slot model period-aware (lunch-only publish validation) — document current behavior; metadata still reflects package `meal_period`

## Decisions

### 1. New public endpoint vs opening `order-menu-preview`

**Choice:** Add `GET /meals/public-package-menu/?meal_public_id=&year=&month=` with `AllowAny` permission.

**Rationale:** Marketing pages are unauthenticated. `order-menu-preview` is scoped to verified customers for the order flow. A dedicated public endpoint:
- Returns only published, customer-visible slot data (same serializer path as preview)
- Does not leak customer/order/subscription data
- Keeps auth semantics clear for order flow

**Alternatives:** Change `order-menu-preview` to `AllowAny` — rejected because it blurs pre-order (authenticated) vs marketing (public) intent and may affect rate-limit/throttle policies later.

### 2. Response shape — shared builder with metadata block

**Choice:** Extend `build_order_menu_preview_for_meal()` into a shared `build_public_package_menu_for_meal()` that returns:

```json
{
  "year": 2026,
  "month": 8,
  "meal_public_id": "uuid",
  "meal_name": "Premium Package",
  "schedule_published": true,
  "meta": {
    "cycle_days": 31,
    "total_meals": 62,
    "meal_period": "both",
    "meal_period_display": "Lunch + Dinner"
  },
  "days": [
    {
      "service_date": "2026-08-01",
      "meal_period": "lunch",
      "ingredients": [{ "id": 1, "name": "Chicken", "product_role": "main" }]
    }
  ]
}
```

Apply the same `meta` block to `my-package-menu` packages[] items and `order-menu-preview`.

**Rationale:** Single source of truth; frontend hero and menu section read one shape. `cycle_days` from `MealCycle.cycle_days`; `meal_period` from `MealCategory.meal_period`.

### 3. Publish gating — server-only

**Choice:** When no published schedule exists, return `200` with `schedule_published: false`, `days: []`, and `meta` still populated from cycle + meal category if cycle exists (or omit meta when meal inactive).

**Rationale:** Matches existing `order-menu-preview` contract. Frontend must not render placeholder meals when unpublished.

### 4. Frontend data adapter

**Choice:** Create `usePublicPackageMenu(mealPublicId, year, month)` hook calling the new public endpoint. In `DetailMenuPlan`:
1. Group `days` by `service_date` using adapted `buildPlanDayRows` logic
2. Filter visible periods by `meta.meal_period` (`lunch` → hide dinner column; `dinner` → hide lunch; `both` → show both)
3. Calendar grid: render only dates present in `days` (service days), not all calendar blanks with fake data
4. Month navigation: pass `year`/`month` to API; disable or show empty when unpublished

**Rationale:** Reuses proven patterns from `MonthlyMenuPage` without duplicating hub-specific delivery/Meal OFF UI.

### 5. Hero duration label

**Choice:** Display `{meta.cycle_days} Days Menu` (localized BN: `{cycle_days} দিনের মেনু`) from menu API meta; fallback to `current_cycle_offering.cycle_days` from meal detail if menu not yet loaded.

**Rationale:** `current_cycle_offering` on meal detail already has `cycle_days` for latest finalized plan; menu meta is authoritative for the selected month.

### 6. Slug resolution unchanged

**Choice:** Keep `useMonthlyPackageBySlug` as-is; pass resolved `pkg.publicId` into menu hook.

**Rationale:** No new slug-based API needed; `meal_public_id` is the stable identifier.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Public endpoint scraped for menu data | Only published menus; no prices or internal IDs beyond ingredient names; consider rate limiting later |
| `meal_period` vs schedule always has lunch+dinner slots | UI filters columns by package period; document that kitchen calendar may still assign both internally |
| Month nav shows empty for unpublished future months | Show "Menu not published yet" copy (reuse `MonthlyMenuPage` Bangla/EN strings) |
| Two menu UIs (marketing vs hub) diverge | Shared types + `buildPlanDayRows` adapter; optional follow-up to extract shared `MonthlyMenuCalendar` component |
| Frontend repo is separate | Tasks include both repos; E2E verification against local `runserver` + `vite` |

## Migration Plan

1. Deploy backend first (additive fields + new public route)
2. Deploy frontend wired to new endpoint
3. Verify Regular and Premium package URLs with published and draft schedules
4. Rollback: frontend can feature-flag back to placeholder; backend changes are backward-compatible

## Open Questions

- Should public endpoint accept `meal_slug` in addition to `meal_public_id`? **Deferred** — slug resolution stays on frontend via existing meals list.
- Rate limiting on public menu endpoint? **Deferred** — not in v1 unless abuse observed.
