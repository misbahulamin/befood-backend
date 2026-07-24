## Why

Public Meal APIs currently expose sequential integer primary keys (`GET /meals/3/`), which leak record counts and make resources easier to enumerate. Customers and storefront clients should address meals only via opaque UUID public identifiers while Django keeps integer PKs for FKs, admin tooling, and internal joins.

## What Changes

- Add `MealCategory.public_id` (`UUIDField`, unique, indexed, auto-generated) while keeping the existing integer `id` as the database primary key.
- **BREAKING:** Public meal list/detail responses replace `id` with read-only `public_id`.
- **BREAKING:** Meal detail/update/delete URLs use `/meals/<uuid:public_id>/` instead of `/meals/<int:pk>/`. Integer path lookups return 404.
- Safe data migration populates `public_id` for existing rows without deleting or recreating meal data.
- Public meal serializers keep customer-facing fields (name, prices, thumbnail, description, menu offering) and stop exposing internal integer IDs and admin costing internals (`plan_id`, `product_cost`, `profit`) on public offering payloads.
- Admin / manager meal and cycle APIs retain internal integer IDs where useful for operations.
- Customer order create accepts meal identity by `public_id` (not sequential meal PK) so the storefront can place orders after browsing UUID-based meal URLs.
- Tests, OpenAPI, and frontend/backend docs updated for the new contract.

## Capabilities

### New Capabilities
- `meal-public-identifiers`: UUID `public_id` on `MealCategory`, public meal routing/lookup by UUID, public vs admin serializer field rules, and customer order meal reference by public UUID.

### Modified Capabilities
- (none in `openspec/specs/` — public meal offering behavior lives only in prior change artifacts; new requirements are captured under `meal-public-identifiers`)

## Impact

- **Models:** `meals.models.MealCategory` (+ migration with backfill).
- **Public Meal API:** `meals/api/serializers.py`, `meals/api/views.py` (`lookup_field` / `lookup_url_kwarg`), router URL shape under `meals/api/urls.py` and `core/urls.py` include path `/meals/`.
- **Public offering payload:** `meals/services/meal_offering.py` (`build_public_cycle_offering`).
- **Orders create contract:** `orders/api/serializers.py` (`OrderCreateSerializer` meal reference).
- **Nested / related responses to evaluate:** `MealCategoryBriefSerializer`, today-menu `meal_category_id`, menu-schedule serializers — public/customer surfaces switch to `public_id` where meal identity is exposed; admin cycle APIs may keep integer FKs.
- **Admin:** Django admin can show `public_id` as read-only; PK remains integer.
- **Clients:** Any frontend/mobile using `/meals/{id}/`, `meal.id`, or order `meal_id` as integer must migrate to `public_id`.
- **Tests:** `meals/tests/test_meals.py`, order tests that pass `meal_id`, any hard-coded `/meals/<int>/` URLs.
