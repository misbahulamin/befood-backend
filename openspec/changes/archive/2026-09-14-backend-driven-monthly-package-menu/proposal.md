## Why

The public monthly-package detail pages (`/monthly-package/Premium-Package`, `/monthly-package/Regular-Package`) render a **100% placeholder** calendar/list menu while the backend already publishes real monthly schedules. Marketing visitors cannot see the actual published menu, duration (30/31 days), or meal option (single/both) without duplicating hardcoded data. This creates a misleading UX and blocks the product goal of backend-driven package pages.

## What Changes

- Add a **public read API** for published monthly package menus (by `meal_public_id` or slug-resolvable package identity) so unauthenticated marketing pages can load real menu data.
- Extend customer menu responses (`order-menu-preview`, `my-package-menu`) with **package metadata**: `cycle_days`, `total_meals`, `meal_period`, `meal_period_display`, and `package_name` so the frontend does not hardcode "30/31 days" or meal-option labels.
- Wire frontend `DetailMenuPlan` (calendar + list views) to the public menu API with proper **publish gating** (`schedule_published === false` → friendly empty state).
- Replace hardcoded hero facts (duration, meal option) with API-driven values from meal detail + menu metadata.
- Respect `meal_period` when rendering slots (lunch-only packages hide dinner column).
- Add loading and error states on monthly-package detail menu section.
- Update OpenAPI docs and frontend integration docs.
- Add backend and frontend tests for published/unpublished flows for Regular and Premium packages.

**Non-breaking:** Existing authenticated endpoints keep their response shape; new fields are additive. Flat `days[]` list is preserved for backward compatibility.

## Capabilities

### New Capabilities

- `public-monthly-package-menu`: Unauthenticated read of a published monthly menu for an active meal package, with publish gating enforced server-side and metadata for calendar/list UI.

### Modified Capabilities

- `customer-meal-package-menu`: Add optional `meta` block (`cycle_days`, `total_meals`, `meal_period`, `meal_period_display`) to `order-menu-preview` and `my-package-menu` responses for consistent frontend rendering.

## Impact

**Backend (`befood-backend`):**
- `meals/services/package_menu.py` — extend builders with metadata
- `meals/api/menu_schedule_views.py` — new public view or permission change
- `meals/api/urls.py` — new route
- `meals/docs/frontend/` — integration doc update
- `meals/tests/` — new/updated tests

**Frontend (`befood-frontend`):**
- `src/features/monthly-package/components/detail/DetailMenuPlan.tsx` — replace placeholder with API data
- `src/features/monthly-package/components/detail/DetailHero.tsx` — dynamic duration/meal option
- `src/features/monthly-package/pages/MonthlyPackageDetailPage.tsx` — pass `publicId`, wire hooks
- New hook/API module for public monthly menu (or extend existing `orderMenuPreviewApi`)
- Remove dependency on `buildPlaceholderMenuDays()` for production menu rendering

**Systems:** No database schema changes expected. Publish workflow unchanged. Order/subscribe flows unaffected.
