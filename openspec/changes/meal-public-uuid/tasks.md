## 1. Model and migration

- [x] 1.1 Add `import uuid` and `public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)` on `MealCategory` in `meals/models.py`
- [x] 1.2 Create a safe migration that adds `public_id`, backfills existing rows with unique UUIDs, and enforces non-null unique constraint without deleting meal data
- [x] 1.3 Expose read-only `public_id` on `MealCategoryAdmin` (list/detail) without making it editable

## 2. Public meal API contract

- [x] 2.1 Update `MealListSerializer` / `MealDetailSerializer` to replace `id` with read-only `public_id`
- [x] 2.2 Set `lookup_field = "public_id"` (and matching URL kwarg) on `MealCategoryViewSet`
- [x] 2.3 Confirm router detail routes resolve as `/meals/<uuid>/` and integer paths no longer retrieve meals
- [x] 2.4 Update OpenAPI/`extend_schema` notes for UUID path parameter and response fields

## 3. Public offering and related serializers

- [x] 3.1 Update `build_public_cycle_offering` to omit `plan_id`, `product_cost`, and `profit` (and aligned internal cost bands per design)
- [x] 3.2 Review `MealCategoryBriefSerializer` and customer-facing nested payloads (e.g. today-menu); expose `public_id` instead of integer meal id on customer surfaces; leave admin cycle integer FKs intact
- [x] 3.3 Preserve listing, pricing, cycle offering (customer-safe), create/update/soft-delete behavior

## 4. Orders customer meal reference

- [x] 4.1 Change `OrderCreateSerializer` to accept `meal_public_id` (UUID) and resolve via `MealCategory.public_id`
- [x] 4.2 Update customer order response serializers if they expose integer meal identity so clients see `meal_public_id` / nested `public_id`
- [x] 4.3 Update order OpenAPI examples and validation error field names

## 5. Tests

- [x] 5.1 Update `meals/tests/test_meals.py` for `public_id` in responses, UUID detail URLs, and failed integer-path lookup
- [x] 5.2 Update order tests that pass `meal_id` to use `meal_public_id`
- [x] 5.3 Add/adjust tests asserting public offering omits `plan_id` / `product_cost` / `profit`
- [x] 5.4 Run `python manage.py makemigrations` / `migrate` and targeted meals + orders tests

## 6. Documentation

- [x] 6.1 Write `meals/docs/frontend/meal-public-uuid.md` with breaking changes, URL/examples, order create, and frontend checklist
- [x] 6.2 Write `meals/docs/backend/meal-public-uuid.md` covering model, migration, lookup, and serializer split
- [x] 6.3 Cross-link from related meal/order frontend docs if they still mention integer meal `id`
