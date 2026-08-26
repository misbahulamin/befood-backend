## Why

Admins publish a monthly menu schedule for a specific **cycle month** (e.g. September 2026), but the public marketing page (`/monthly-package/Student-Package`) defaults to the **current calendar month** (August 2026). Production verification shows the backend is correct: Student Package September 2026 returns `schedule_published: true` with 60 day slots, while August 2026 returns `schedule_published: false`. The frontend therefore shows "Not published yet" even though a menu exists — because the user is viewing the wrong month, not because publish failed.

This is a **discovery / default-month UX gap**, not a broken publish pipeline. Operators and customers need the site to surface the published menu without manual month hunting, and admins need confidence that "published" on the schedule page matches what visitors see.

## What Changes

- **Investigation (read-only):** Document production API verification for Student Package Aug/Sep 2026 and confirm no backend publish bug.
- **Backend (additive, non-destructive):** Extend `GET /meals/public-package-menu/` response with optional `published_months` or `nearest_published` hint so clients can auto-navigate to a month that has a published schedule. No changes to publish/unpublish logic, no migrations, no data deletion.
- **Frontend (`befood-frontend`):** On `DetailMenuPlan` load, when the selected month is unpublished, auto-select the nearest published month (prefer current or next) using the new API hint; show a clear banner ("Showing September menu — August not published yet").
- **Frontend:** Keep month picker manual override; do not wipe or mutate schedule data.
- **Docs:** Update `meals/docs/frontend/public-monthly-package-menu.md` with discovery workflow and troubleshooting (month mismatch).
- **Tests:** Backend tests for new hint fields; frontend tests for auto-month selection and fallback to empty state when no month is published.

**Non-breaking:** Existing `schedule_published`, `days`, and `meta` fields unchanged. New fields are additive.

## Capabilities

### New Capabilities

_(none — behavior extends existing public menu capability)_

### Modified Capabilities

- `public-monthly-package-menu` (delta under `openspec/changes/backend-driven-monthly-package-menu/specs/` lineage): Response MAY include published-month discovery metadata so clients can default to a visible menu without guessing.
- `monthly-menu-schedule`: Clarify that publish is scoped to the linked cycle's `(year, month)`; customer visibility requires querying that same month.

## Impact

| Area | Files / systems |
| --- | --- |
| Backend service | `meals/services/package_menu.py` — add published-month lookup helper |
| Backend API | `meals/api/menu_schedule_views.py` — extend `PublicPackageMenuView` response |
| Backend tests | `meals/tests/test_public_package_menu.py` |
| Backend docs | `meals/docs/frontend/public-monthly-package-menu.md` |
| Frontend | `befood-frontend/src/features/monthly-package/components/detail/DetailMenuPlan.tsx`, `usePublicPackageMenu`, types |
| Production data | **No migration, no deletes, no republish required** |
| Admin workflow | Unchanged; admins still publish per cycle month |

**Root cause (verified on production 2026-08-27):**

| Package | Month | `schedule_published` | Days |
| --- | --- | --- | --- |
| Student Package | 2026-08 | `false` | 0 |
| Student Package | 2026-09 | `true` | 60 |
| Regular / Premium | 2026-08, 2026-09 | `false` | 0 |

Admin screenshot: September 2026 schedule **published**. Frontend screenshot: August 2026 **not published** — matches API.
