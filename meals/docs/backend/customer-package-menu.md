# Customer Package Menu (Backend)

## Summary

Customer-facing read API that returns the full published monthly lunch/dinner menu for the authenticated customer's meal package(s) in a target calendar month.

- Route: `GET /meals/my-package-menu/`
- View: `CustomerPackageMenuView` in `meals/api/menu_schedule_views.py`
- Service: `meals/services/package_menu.py`
- Permission: `IsVerifiedCustomer`
- No DB migration (reuses existing menu + order models)

## Resolution rules

1. Resolve `year`/`month` from query params (both together) or default to `timezone.localdate()` month.
2. Load non-cancelled `Order` rows for `customer` where `order_month == YYYY-MM`.
3. For each order, load published `MonthlyMenuSchedule` where:
   - `plan.meal_category_id == order.meal_id`
   - `plan.cycle.year/month` match target month
   - `status == published`
4. Serialize all slots via `serialize_schedule_assignments` (no reveal-time gating).
5. If no published schedule: still return package identity with `schedule_published: false` and `days: []`.

Ownership is enforced by querying only the caller's orders (no client-supplied meal id authorization).

## Key models

| Model | Role |
|-------|------|
| `Order` | Links customer → `MealCategory` for a month |
| `MealCategory` | Meal package |
| `MealCycle` / `MealCyclePlan` | Monthly cycle + package plan |
| `MonthlyMenuSchedule` | Published/draft menu container |
| `MonthlyMenuSlot` / `MonthlyMenuSlotItem` | Per-day lunch/dinner ingredients |

## Service API

| Function | Role |
|----------|------|
| `resolve_target_year_month` | Validate/default year+month; raises `ValidationError` |
| `orders_for_customer_month` | Non-cancelled orders for `YYYY-MM` |
| `published_schedule_for_meal` | Published schedule lookup |
| `build_package_menu_for_customer` | Full response payload |

## Separation from today-menu

`build_today_menu_for_customer` still applies `MenuRevealSettings` lunch/dinner reveal times and returns only today's visible periods. Package menu intentionally does **not** call reveal helpers.

## How to verify

```bash
python manage.py test meals.tests.test_customer_package_menu
```

Swagger: tag **Customer Package Menu**, path `/meals/my-package-menu/`.

Frontend contract: `meals/docs/frontend/customer-package-menu.md`.

OpenSpec change: `openspec/changes/add-customer-meal-package-menu-api/`.
