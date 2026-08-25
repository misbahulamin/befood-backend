## 1. Backend — Menu metadata helper

- [x] 1.1 Add `build_menu_meta(meal, year, month)` in `meals/services/package_menu.py` returning `cycle_days`, `total_meals`, `meal_period`, `meal_period_display`
- [x] 1.2 Refactor `build_order_menu_preview_for_meal()` to include `meta` in response
- [x] 1.3 Add `meta` to each package entry in `build_package_menu_for_customer()`

## 2. Backend — Public package menu endpoint

- [x] 2.1 Add `build_public_package_menu_for_meal(meal, year, month)` service function (published-only, no customer data)
- [x] 2.2 Add `PublicPackageMenuView` in `meals/api/menu_schedule_views.py` with `AllowAny` permission
- [x] 2.3 Register route `GET /meals/public-package-menu/` in `meals/api/urls.py`
- [x] 2.4 Add OpenAPI schema (parameters, 200/400/404 responses) via `@extend_schema`
- [x] 2.5 Validate `meal_public_id` required; reject inactive meals with `404`

## 3. Backend — Tests and docs

- [x] 3.1 Add tests in `meals/tests/` for public endpoint: published menu, unpublished empty days, invalid month, unknown meal, meta fields
- [x] 3.2 Add tests for `meta` on `order-menu-preview` and `my-package-menu` responses
- [x] 3.3 Update `meals/docs/frontend/customer-package-menu.md` with public endpoint and `meta` block
- [x] 3.4 Add `meals/docs/frontend/public-monthly-package-menu.md` integration guide for marketing pages

## 4. Frontend — API layer and types

- [x] 4.1 Add `PublicPackageMenuResponse` types in `src/features/meals/types/` (or monthly-package types)
- [x] 4.2 Add `getPublicPackageMenu()` API function calling `GET /meals/public-package-menu/`
- [x] 4.3 Add `usePublicPackageMenu(mealPublicId, year, month)` React Query hook with loading/error states
- [x] 4.4 Extend `OrderMenuPreviewResponse` types with optional `meta` block for consistency

## 5. Frontend — Menu data adapter

- [x] 5.1 Create `mapPublicMenuToPlanRows(days, mealPeriod)` utility (adapt from `monthlyMenuPlan.ts` `buildPlanDayRows`)
- [x] 5.2 Add helper to derive visible periods from `meta.meal_period` (`lunch` | `dinner` | `both`)
- [x] 5.3 Add helper for duration label: `{cycle_days} Days Menu` / localized BN equivalent

## 6. Frontend — DetailMenuPlan integration

- [x] 6.1 Pass `mealPublicId` from `MonthlyPackageDetailPage` into `DetailMenuPlan`
- [x] 6.2 Replace `buildPlaceholderMenuDays()` with `usePublicPackageMenu` data
- [x] 6.3 Implement unpublished state UI (no fake meals; friendly message when `schedule_published === false`)
- [x] 6.4 Wire calendar view to grouped API day rows (service dates only)
- [x] 6.5 Wire list view to same grouped rows
- [x] 6.6 Filter lunch/dinner columns by `meta.meal_period`
- [x] 6.7 Add loading skeleton and error retry UI
- [x] 6.8 Connect month navigation (`cursor` state) to API `year`/`month` params

## 7. Frontend — DetailHero and labels

- [x] 7.1 Replace hardcoded "৩০/৩১ দিন" with dynamic `meta.cycle_days` from menu hook (fallback to `current_cycle_offering.cycle_days`)
- [x] 7.2 Ensure meal option chip uses `meta.meal_period_display` or existing `mealPeriodLabel` from meal detail
- [x] 7.3 Remove or update "Demo Menu · API-ready" badge to reflect real publish status

## 8. End-to-end verification

- [x] 8.1 Start backend (`python manage.py runserver`) and frontend (`npm run dev`)
- [x] 8.2 Verify `/monthly-package/Regular-Package`: published menu, correct days count, meal option, calendar view, list view
- [x] 8.3 Verify `/monthly-package/Premium-Package`: same checks
- [x] 8.4 Verify unpublished month shows empty state (no placeholder dishes)
- [x] 8.5 Confirm existing `/account/monthly-menu` and order flow still work (no regression)
