## 1. Service layer

- [x] 1.1 Add `build_package_menu_for_customer` (and helpers) in `meals/services/` to resolve the customer's non-cancelled orders for a target year/month and load published `MonthlyMenuSchedule` slots/items
- [x] 1.2 Serialize lean day slots (`service_date`, `meal_period`, ingredients with `id`/`name`/`product_role`) without reveal-time gating; return `schedule_published` false + empty days when unpublished/missing
- [x] 1.3 Validate optional `year`/`month` (both required together; month 1–12) and default to current local month when omitted

## 2. API endpoint

- [x] 2.1 Add `CustomerPackageMenuView` (`GET`) with `IsVerifiedCustomer`, thin view calling the service
- [x] 2.2 Wire `GET /meals/my-package-menu/` in `meals/api/urls.py`
- [x] 2.3 Add OpenAPI/`extend_schema` for query params and response shape

## 3. Tests

- [x] 3.1 Test verified customer with published schedule receives full month lunch/dinner slots
- [x] 3.2 Test unpublished/missing schedule returns package with `schedule_published=false` and empty days
- [x] 3.3 Test no active order returns empty `packages`
- [x] 3.4 Test unauthenticated request returns `401`
- [x] 3.5 Test invalid `year`/`month` query returns `400`
- [x] 3.6 Confirm `today-menu` reveal behavior remains unchanged (existing or smoke assertion)

## 4. Documentation

- [x] 4.1 Add `meals/docs/frontend/customer-package-menu.md` with auth, query params, success/error examples, and UI states
- [x] 4.2 Add `meals/docs/backend/customer-package-menu.md` covering models, resolution rules, and verification steps
