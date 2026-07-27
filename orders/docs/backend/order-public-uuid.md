# Backend: Order + Delivery public UUID

## Models

- `Order(PublicIdMixin)` and `OrderDelivery(PublicIdMixin)` — integer PK retained
- Migration: `orders.0006_order_public_id`

## API

| ViewSet | lookup |
|---------|--------|
| `MealOrderViewSet` | `public_id` |
| `AdminOrderViewSet` | `public_id` |

Delivery nested actions resolve `delivery_id` path segment via `OrderDelivery.public_id`.

## Serializers

- Customer/admin order list/detail: `public_id` (no integer order `id`)
- Nested deliveries: `public_id`
- Today board: `public_id`, `order_public_id`
- Today menu packages: `order_public_id`

Admin list may still include integer `meal` FK plus `meal_public_id`.

## Verify

```bash
python manage.py migrate orders
python manage.py test orders.tests
```
