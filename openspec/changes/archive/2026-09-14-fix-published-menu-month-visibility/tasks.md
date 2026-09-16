## 1. Investigation verification (read-only)

- [x] 1.1 Re-run production API checks for Student Package Aug/Sep 2026 (`schedule_published`, `days` count) and record results in PR notes
- [x] 1.2 Confirm admin published schedule cycle month matches frontend `cursor` month (no backend publish bug)

## 2. Backend — published-month discovery helper

- [x] 2.1 Add `list_published_months_for_meal(meal_id)` in `meals/services/package_menu.py` returning sorted `{year, month}` list from published schedules
- [x] 2.2 Add `nearest_published_month(meal_id, year, month)` using distance + future tie-break per design
- [x] 2.3 Extend `build_public_package_menu_for_meal()` to include `nearest_published_month` and `published_months` in response (requested month payload unchanged)

## 3. Backend — API and OpenAPI

- [x] 3.1 Update `PublicPackageMenuView` `@extend_schema` with new response fields and examples
- [x] 3.2 Ensure `400`/`404` paths unchanged; no auth changes

## 4. Backend — tests and docs

- [x] 4.1 Add tests in `meals/tests/test_public_package_menu.py`: requested month published, unpublished with future published month, no published months, multiple published months
- [x] 4.2 Update `meals/docs/frontend/public-monthly-package-menu.md` with discovery fields, auto-nav workflow, and admin troubleshooting (cycle month vs current month)

## 5. Frontend — types and API

- [x] 5.1 Extend `PublicPackageMenuResponse` with `nearest_published_month` and `published_months`
- [x] 5.2 Verify `getPublicPackageMenu` passes through new fields without breaking existing consumers

## 6. Frontend — DetailMenuPlan UX

- [x] 6.1 On first load, if `schedule_published === false` and `nearest_published_month` is set, auto-update `cursor` once (ref guard)
- [x] 6.2 Add info banner when showing a month different from user's current month or after auto-redirect from unpublished current month
- [x] 6.3 Keep manual prev/next month navigation; do not auto-override after initial redirect
- [x] 6.4 Add unit/integration test for auto-navigation and banner visibility

## 7. End-to-end verification

- [x] 7.1 Local/staging: `/monthly-package/Student-Package` loads September menu when August unpublished
- [x] 7.2 Manual month navigation still works; unpublished months show empty state with banner
- [x] 7.3 Confirm no schedule data modified (read-only API + frontend state only)
