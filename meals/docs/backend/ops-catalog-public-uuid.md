# Backend: Ops catalog public UUID

Models with `PublicIdMixin`: `Ingredient`, `MealCycle`, `MealCyclePlan`, `MealCyclePlanLine`, `MonthlyMenuSchedule`.

Migration: `meals.0011_ops_catalog_public_id`.

ViewSets use `lookup_field = "public_id"`. Serializers expose `public_id` alongside integer `id` for transitional admin FK filters/writes.
