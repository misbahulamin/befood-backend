## Context

Production investigation (2026-08-27) confirmed the publish pipeline works:

```
GET /meals/public-package-menu/?meal_public_id=c8c12444-...&year=2026&month=8
→ schedule_published: false, days: []

GET /meals/public-package-menu/?meal_public_id=c8c12444-...&year=2026&month=9
→ schedule_published: true, days: 60
```

Admin UI shows Student Package **September 2026** schedule as `published`. Marketing page `/monthly-package/Student-Package` defaults `cursor` to `new Date()` → August 2026 and correctly shows "Not published yet" for that month.

`published_schedule_for_meal()` in `meals/services/package_menu.py` filters by:

- `plan__meal_category_id = meal.id`
- `plan__cycle__year` / `plan__cycle__month`
- `status = published`

No bug found in publish, unpublish, or public read paths. The gap is **month discovery**: clients must know which `(year, month)` to query.

`DetailMenuPlan.tsx` already wires month navigation to API params; users must manually click → to reach September. No data loss risk from this fix — all changes are read-only hints and frontend defaulting.

## Goals / Non-Goals

**Goals:**

- Visitors landing on a package page see the published menu when one exists for a nearby month, without admin intervention.
- API exposes lightweight discovery metadata (`nearest_published_month`, `published_months`) on every public menu response.
- Frontend auto-selects nearest published month on first load when current month is unpublished; user can still navigate manually.
- Clear UI copy when viewing a different month than "today" (e.g. banner: "August menu not published — showing September").
- Regression tests for backend hints and frontend auto-navigation.
- Document troubleshooting for admins (publish is per cycle month).

**Non-Goals:**

- Auto-publishing August or any month without admin action.
- Changing publish/unpublish validation, slot data, or price snapshots.
- Database migrations or backfills.
- Replacing month picker with a single "latest only" view.
- Fixing unrelated admin reopen/schedule deletion (tracked separately in `preserve-menu-schedule-on-plan-reopen`).

## Decisions

### 1. Add discovery fields to existing public endpoint (not a new route)

**Choice:** Extend `GET /meals/public-package-menu/` response with:

```json
{
  "nearest_published_month": { "year": 2026, "month": 9 },
  "published_months": [{ "year": 2026, "month": 9 }]
}
```

Both fields are always present for an active meal. `nearest_published_month` is `null` when no published schedule exists. `published_months` is sorted ascending by `(year, month)`.

**Alternatives considered:**

| Alternative | Why rejected |
| --- | --- |
| New `GET /meals/public-package-menu/published-months/` | Extra round-trip; frontend already calls public menu |
| Frontend scans ±6 months with repeated API calls | Slow, noisy, race-prone |
| Default backend to "latest published" when month omitted | **BREAKING** — changes semantics of omitted year/month (currently = current local month) |

### 2. Nearest-month selection algorithm

**Choice:** Given requested `(year, month)`:

1. If that month is published → `nearest_published_month` equals requested month.
2. Else find the published month minimizing `abs(months_between(requested, candidate))`; tie-break toward **future** month (customers care about upcoming menus).
3. If no published months exist → `nearest_published_month: null`.

Implementation: single query on `MonthlyMenuSchedule` filtered by `plan__meal_category_id`, `status=published`, ordered by `plan__cycle__year`, `plan__cycle__month`. Limit scan to ±12 months from requested for performance (configurable constant).

### 3. Frontend auto-navigation (opt-in on first paint only)

**Choice:** In `DetailMenuPlan`:

1. Initial `cursor` = current local month (unchanged).
2. After first successful fetch, if `!schedule_published` and `nearest_published_month` is set, update `cursor` once to that month (use `useRef` guard to avoid loops).
3. Show info banner when `cursor` ≠ user's "natural" current month OR when auto-redirected from unpublished current month.

Manual prev/next month navigation never auto-overrides after initial redirect.

**Alternative:** Deep-link `?year=2026&month=9` in URL — deferred; not required for this fix.

### 4. No changes to publish workflow or data

**Choice:** Read-only metadata only. No `publish_schedule()` / `unpublish_schedule()` edits.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| User expects August menu but only September published | Banner explains month mismatch; admin docs clarify cycle month |
| `published_months` list grows over years | Cap list at 24 entries or ±12 months window; document in OpenAPI |
| Auto-redirect surprises user browsing historical months | Only runs once on initial load; manual navigation respected |
| Extra DB query per public menu request | Indexed filter on `(meal_category, cycle year/month, status)`; prefetch with existing schedule lookup |

## Migration Plan

1. Deploy backend with additive response fields (backward compatible).
2. Deploy frontend with auto-navigation + banner.
3. No rollback data risk — remove frontend auto-nav if needed; old clients ignore new fields.

**Immediate operator workaround (no deploy):** On marketing page, click → to September 2026, or publish August schedule in admin if that month should be live.

## Open Questions

- Should `order-menu-preview` and `my-package-menu` get the same hints for consistency? **Defer** — marketing page is the reported issue; can extend later additively.
- Should URL reflect selected month (`?year=&month=`)? **Defer** — nice-to-have for shareable links.
