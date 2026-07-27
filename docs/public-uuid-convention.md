# Public UUID convention (project-wide)

BeFood keeps integer database primary keys and exposes opaque UUID `public_id` values to clients.

## Field

Use `PublicIdMixin` from `core.models` (same shape as `MealCategory.public_id`):

```python
public_id = models.UUIDField(
    default=uuid.uuid4,
    editable=False,
    unique=True,
    db_index=True,
)
```

## Rules

| Concern | Rule |
|---------|------|
| DB PK / FKs | Integer (internal) |
| Customer/public response identity | `public_id` only (no integer `id`) |
| Nested / request references | `{resource}_public_id` (e.g. `meal_public_id`, `order_public_id`) |
| Detail URL lookup | `lookup_field = "public_id"` |
| Dual int+UUID routes | Not supported after cutover |
| Migration | nullable add → backfill → unique non-null |

## Phases

See OpenSpec change `project-wide-public-uuid`:

0. Meals — done (`meals/docs/frontend/meal-public-uuid.md`)
1. Orders + deliveries — done (`orders/docs/frontend/order-public-uuid.md`)
2. Customer addresses — done (`user_management/docs/frontend/address-public-uuid.md`)
3. Ops catalog — done (`meals/docs/frontend/ops-catalog-public-uuid.md`); write FKs like `plan_id` may still be integer
4. Stub apps — UUID-first before mount (`docs/deferred-domain-public-uuid.md`)

### Inventory note (Phase 0 confirmation)

Already UUID: `MealCategory.public_id`, order create `meal_public_id`, today-menu meal identity.

Migrated in this change: `Order`, `OrderDelivery`, `CustomerAddress`, ops catalog models above.

Still integer (by design for now): Django `User.id`, admin `customer_id`, ingredient ids inside menu slot payloads, write FK `plan_id` on schedule create.

## Related

- OpenSpec: `openspec/changes/project-wide-public-uuid/`
- Meal example: `meals/docs/frontend/meal-public-uuid.md`
