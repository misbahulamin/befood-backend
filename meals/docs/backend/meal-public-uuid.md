# Backend: Meal public UUID

## Quick summary

| Concern | Behavior |
|---------|----------|
| DB PK | Integer `MealCategory.id` (unchanged) |
| Public identity | `MealCategory.public_id` UUID |
| Public meal URLs | `/meals/<public_id>/` via `lookup_field = "public_id"` |
| Public serializers | `MealListSerializer` / `MealDetailSerializer` expose `public_id`, not `id` |
| Admin cycle brief | `MealCategoryBriefSerializer` keeps `id` and adds `public_id` |
| Order create | `meal_public_id` UUID → resolve `MealCategory.objects.get(public_id=…)` |
| Public offering | No `plan_id` / `product_cost` / `profit` / `other_cost` |

## Endpoint grid

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/meals/` | public | list; `public_id` only |
| GET | `/meals/{public_id}/` | public | detail + offering |
| POST | `/meals/` | manager | create; response uses detail serializer |
| PATCH | `/meals/{public_id}/` | manager | update |
| DELETE | `/meals/{public_id}/` | manager | soft deactivate |
| POST | `/orders/` | verified customer | body `meal_public_id` |

## Model / migration

- Field: `public_id = UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)`
- Migration `0010_mealcategory_public_id`: add nullable → backfill → alter unique non-null
- Existing rows keep integer PK; data is not deleted/recreated

## Serializer split

**Public (customer):** `meals/api/serializers.py` — no integer `id`.

**Admin/manager cycle:** `MealCategoryBriefSerializer` — `id` + `public_id`.

**Orders customer:** `meal_public_id` on create + list/detail; admin order list still has integer `meal` FK plus `meal_public_id`.

**Today menu:** `meals/services/today_menu.py` returns `meal_public_id` per package.

## Permissions

Unchanged: public GET list/retrieve; manager groups for write; customer verified for order create.

## How to verify

```bash
python manage.py migrate meals
python manage.py test meals.tests.test_meals meals.tests.test_meal_cycle_api orders.tests.test_orders
```

Manual:

1. `GET /meals/` → each row has `public_id`, no `id`
2. `GET /meals/<uuid>/` → 200
3. `GET /meals/<int-pk>/` → 404
4. `POST /orders/` with `meal_public_id` → 201

## Related

- Frontend integrator guide: [`../frontend/meal-public-uuid.md`](../frontend/meal-public-uuid.md)
- OpenSpec: `openspec/changes/meal-public-uuid/`
