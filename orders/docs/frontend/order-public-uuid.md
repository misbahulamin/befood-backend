# Frontend: Order + Delivery public UUID

## Summary

**Breaking:** Orders and deliveries no longer expose sequential integer `id` on customer/web APIs. Use UUID `public_id` everywhere.

| Before | After |
|--------|--------|
| `GET /orders/12/` | `GET /orders/<uuid>/` |
| Order field `id` | `public_id` |
| Delivery field `id` | `public_id` |
| Today-board `order_id` / delivery `id` | `order_public_id` / `public_id` |
| Today-menu `order_id` | `order_public_id` |
| Meal-off / mark paths with int ids | UUID order + delivery in path |

Meal catalog identity remains `meal_public_id` (see meal-public-uuid docs).

## Paths

```http
GET    /orders/
GET    /orders/{order_public_id}/
POST   /orders/{order_public_id}/cancel/
POST   /orders/{order_public_id}/deliveries/{delivery_public_id}/meal-off
POST   /api/v1/web/orders/{order_public_id}/deliveries/{delivery_public_id}/mark
GET    /api/v1/web/orders/today-board/
```

Path param name in OpenAPI/router is `public_id` for the order; delivery segment is still named `delivery_id` but the **value must be the delivery UUID** (`public_id`).

## Create order (unchanged field name from meal UUID work)

```json
{ "meal_public_id": "<meal-uuid>", "customer_note": "" }
```

Response includes order `public_id` and nested deliveries each with `public_id`.

## Frontend checklist

- [ ] Store `order.public_id` and `delivery.public_id`
- [ ] Replace all `/orders/{number}/` routes
- [ ] Meal-off / mark-delivery use both UUIDs
- [ ] Today board: use `order_public_id` + delivery `public_id`
- [ ] Today menu: use `order_public_id`
- [ ] Expect 404 on old integer order URLs

## Related

- Convention: [`docs/public-uuid-convention.md`](../../../docs/public-uuid-convention.md)
- Backend: [`../backend/order-public-uuid.md`](../backend/order-public-uuid.md)
- Full order process: [`full-order-process.md`](full-order-process.md)
- Meal-off: [`customer-meal-off.md`](customer-meal-off.md)
- Meals: [`../../../meals/docs/frontend/meal-public-uuid.md`](../../../meals/docs/frontend/meal-public-uuid.md)
