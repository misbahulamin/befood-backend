## Context

BeFood already migrated meal packages to UUID `public_id` (`meal-public-uuid`). Live mounted APIs under `core/urls.py` are:

- `user_management/` — auth, profile, `customer/addresses`
- `meals/` — packages (UUID done), cycles/ingredients/schedules (integer), today-menu
- `orders/` + `api/v1/web/orders/` — order CRUD, deliveries, meal-off, today-board

Other apps (`wallet`, `payments`, `delivery`, `promotions`, `notifications`, `business`) have models/ViewSet stubs but are not mounted yet.

Stakeholders: customers (opaque IDs), admin/ops (stable tooling), frontend teams (phased breaking contracts).

## Goals / Non-Goals

**Goals:**

- One reusable `public_id` pattern across the project (copy meal approach).
- Phase 1: eliminate sequential IDs from customer-reachable order/delivery/address contracts.
- Later phases: admin meal-ops URLs and stub domains ship UUID-first.
- Keep integer PKs for FKs, constraints, admin DB, and internal joins.
- Document each phase for frontend AI/integrators.

**Non-Goals:**

- Replacing Django `User.id` or auth token schemes.
- Dual-routing (accept both int and UUID) after a phase cuts over.
- Rewriting business logic of orders/meals/auth.
- Shipping full wallet/payments APIs in this change (only readiness rules).

## Decisions

### 1. Standard field (copy meal)

```python
public_id = models.UUIDField(
    default=uuid.uuid4,
    editable=False,
    unique=True,
    db_index=True,
)
```

**Rationale:** Proven on `MealCategory`; DRF lookup + UUID path validation work.

**Alternatives:** UUID PK — rejected (FK churn). ULID/nanoid — rejected (extra deps, less standard).

### 2. Naming for references

| Role | Field name |
|------|------------|
| Resource self identity in responses | `public_id` |
| Nested / request reference to another resource | `{resource}_public_id` (e.g. `order_public_id`, `delivery_public_id`, `address_public_id`) |
| Admin-only may retain | integer `id` / FK when explicitly admin |

**Rationale:** Matches `meal_public_id` already shipped.

### 3. Phased inventory (priority)

| Phase | Models | Why first |
|-------|--------|-----------|
| **0 (done)** | `MealCategory` | Catalog enumeration |
| **1** | `Order`, `OrderDelivery` | Highest customer URL volume; meal-off + cancel + detail |
| **2** | `CustomerAddress` | Customer CRUD by id |
| **3 (optional)** | `Ingredient`, `MealCycle`, `MealCyclePlan`, `MealCyclePlanLine`, `MonthlyMenuSchedule` | Admin-only today; do when manager UIs need opaque URLs |
| **4 (deferred)** | Wallet/Payment/Delivery/Promo/Notification entities | Add `public_id` on model create **before** mounting public routes |

**Skip / defer identity in URLs:**

- `CustomerProfile` — mostly `/customer/profile/` without path id; if response exposes `id`, replace with `public_id` when touched.
- `MealOffSettings`, `MenuRevealSettings`, `BusinessSettings` — singletons.
- Django `User` — keep integer; never expose as public resource key if avoidable.
- Cart/OrderItem/Review — not primary customer URL resources today.

### 4. Customer vs admin serializers

- **Customer/public:** never return integer PK as `id` for resources that have `public_id`; lookup by `public_id`.
- **Admin web:** prefer `public_id` in URLs for consistency; may include integer `id` **additionally** for ops debugging in Phase 1–2 only if needed—default is UUID-only URLs for both to avoid two client stacks.

**Locked default:** Same UUID lookup for customer and admin order/delivery/address endpoints once Phase 1–2 ships (matches meal soft-delete/update using UUID).

### 5. Nested payloads to update in Phase 1

- Order list/detail: `id` → `public_id`
- Nested deliveries: each delivery `id` → `public_id`
- Today-board / meal-off paths: order & delivery path params → UUID
- Today-menu: `order_id` → `order_public_id` (meal already UUID)

### 6. Shared helper (optional)

Prefer a small mixin/base:

```python
class PublicIdMixin(models.Model):
    public_id = models.UUIDField(...)
    class Meta:
        abstract = True
```

Introduce when Phase 1 starts if it reduces duplication; not required for correctness.

### 7. Stub apps (Phase 4)

When implementing any new ViewSet under wallet/payments/etc.:

1. Add `public_id` on the model in the same PR as the first public serializer.
2. Set `lookup_field = "public_id"`.
3. Do not ship integer `id` on customer serializers.

## Risks / Trade-offs

- [Large breaking surface across apps] → Strict phases; archive/docs per phase; do not big-bang all models.
- [Admin bookmarks with integer order URLs] → Document cutover; 404 on old paths intentionally.
- [Missed nested integer in a service payload] → Grep checklist in tasks (`order_id`, `delivery_id`, `address_id`).
- [Stub apps mount later with int ids by mistake] → Phase 4 checklist + code review rule in convention spec.
- [UUID verbosity in logs] → Acceptable; log both pk and public_id server-side when useful.

## Migration Plan

Per model/phase:

1. Add nullable `public_id` + RunPython backfill + alter unique non-null.
2. Deploy API cutover (serializers + `lookup_field` + nested refs).
3. Ship frontend doc for that phase.
4. Rollback API first if needed; leave DB column in place.

Overall rollout:

1. Phase 1 Orders/Deliveries  
2. Phase 2 Addresses  
3. Phase 3 Ops catalog (optional)  
4. Phase 4 Stub domains on activation  

## Open Questions

- Whether admin order boards keep integer `id` alongside `public_id` for one release — **default no** for customer payloads; admin may keep optional integer for one sprint if ops request it (document if chosen).
- Whether `CustomerProfile.public_id` is needed for admin customer deep-links — defer until an admin customer-detail URL exists.
