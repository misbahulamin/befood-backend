# Frontend: Meal public UUID

## Summary

Meal packages no longer expose sequential integer primary keys on public customer APIs.

**Breaking changes:**

| Before | After |
|--------|--------|
| `GET /meals/3/` | `GET /meals/<uuid>/` |
| Response field `id` (integer) | Response field `public_id` (UUID string) |
| Order create `{ "meal_id": 12 }` | `{ "meal_public_id": "<uuid>" }` |
| Today-menu `meal_category_id` | `meal_public_id` |
| Offering `plan_id`, `product_cost`, `profit`, `other_cost` | Removed from public meal detail |

Internal Django PK still exists in the database. **Do not use it in storefront/mobile clients.**

Target clients: **customer mobile + web**. Admin cycle/plan UIs may still see integer `id` on admin-only endpoints.

---

## What frontend must change

### 1. Meal list

`GET /meals/`

- Store `meal.public_id` (not `meal.id`).
- Navigation / deep links: `/meals/{public_id}` or equivalent route param.
- Remove any code that does `meal.id` for links or order create.

Example list item:

```json
{
  "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "meal_name": "Monthly Package",
  "total_price": "3100.00",
  "per_meal_price": "50.00",
  "pricing_status": "priced",
  "meal_thumbnail": "https://…/thumb.jpg",
  "meal_type": "monthly",
  "meal_type_display": "Monthly",
  "meal_period": "both",
  "meal_period_display": "Both",
  "is_active": true,
  "created_at": "2026-07-01T08:00:00Z",
  "updated_at": "2026-07-10T08:00:00Z"
}
```

There is **no** `id` field on this payload.

### 2. Meal detail

`GET /meals/{public_id}/`

```http
GET /meals/a1b2c3d4-e5f6-7890-abcd-ef1234567890/
```

- Old `GET /meals/3/` returns **404**.
- Detail adds `description` and optional `current_cycle_offering`.

Offering shape (customer-safe):

```json
{
  "year": 2026,
  "month": 4,
  "cycle_days": 30,
  "total_meals": 60,
  "package_total_price": "3100.00",
  "per_meal_rate": "51.67",
  "finalized_at": "2026-03-28T12:00:00Z",
  "menu_items": [
    { "name": "Chicken", "product_role": "main", "servings_count": 60 }
  ]
}
```

**Do not expect:** `plan_id`, `product_cost`, `profit`, `other_cost`.

### 3. Create order (after browsing a meal)

`POST /orders/`

```json
{
  "meal_public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "customer_note": "Ring the bell"
}
```

- Field rename: `meal_id` → `meal_public_id`.
- Value type: UUID string (same as meal detail `public_id`).
- Errors for bad/inactive/unpriced meals appear under `meal_public_id`.

### 4. Order list / detail / current package

Customer order payloads now include:

```json
{
  "id": 1,
  "meal_public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "meal_name_snapshot": "Monthly Package",
  "…"
}
```

- Use `meal_public_id` to deep-link back to meal catalog.
- Integer FK `meal` is **not** on customer serializers anymore.
- Admin web list may still include integer `meal` **plus** `meal_public_id`.

### 5. Today menu (customer)

`GET /meals/today-menu/` package objects:

| Old | New |
|-----|-----|
| `meal_category_id` (int) | `meal_public_id` (UUID string) |

`order_id` remains an integer order PK (unchanged in this release).

### 6. Manager meal CRUD

Create/update/delete still use the same auth rules, but detail URLs use UUID:

```http
PATCH /meals/{public_id}/
DELETE /meals/{public_id}/
```

Create response returns `public_id` (no integer `id`).

---

## Suggested UI workflow

1. `GET /meals/` → render cards keyed by `public_id`.
2. User opens detail → `GET /meals/{public_id}/`.
3. User orders → `POST /orders/` with that same `public_id` as `meal_public_id`.
4. Order screens show `meal_public_id` if linking back to catalog.

```mermaid
flowchart LR
  A[GET /meals/] --> B[Store public_id]
  B --> C[GET /meals/public_id/]
  C --> D[POST /orders/ meal_public_id]
```

---

## Frontend checklist

- [ ] Replace all `/meals/{number}/` routes with UUID param
- [ ] Replace `meal.id` with `meal.public_id` in types/state
- [ ] Update order create body to `meal_public_id`
- [ ] Update order list/detail types: `meal` → `meal_public_id`
- [ ] Update today-menu types: `meal_category_id` → `meal_public_id`
- [ ] Stop rendering/using offering `plan_id` / cost bands if previously shown
- [ ] Handle 404 when old bookmarked integer meal URLs are opened
- [ ] Confirm TypeScript/API client regenerates from OpenAPI if used

---

## Auth / headers

- Public list/detail: no auth
- Order create: customer Token auth (unchanged)
- Optional: `X-Client-Type: mobile|web` if your client already sends it

---

## Related docs

- Backend notes: [`../backend/meal-public-uuid.md`](../backend/meal-public-uuid.md)
- Orders flow: [`../../../orders/docs/frontend/full-order-process.md`](../../../orders/docs/frontend/full-order-process.md)
- Meal period fields: [`package-meal-period.md`](package-meal-period.md)
