## Why

`MealCategory` already uses opaque UUID `public_id` for public meal APIs, but the rest of BeFood still exposes sequential integer primary keys on customer and ops URLs (`/orders/12/`, address IDs, delivery slot IDs). That leaves the same enumeration and information-leak risks, and creates an inconsistent client contract. Now that the meal pattern is proven, the project needs a single phased plan to roll UUID public identifiers across every client-facing resource—and to apply the same convention to stub apps before they ship.

## What Changes

- Adopt a **project-wide public UUID convention** (same shape as `MealCategory.public_id`): keep integer DB PKs/FKs; add `public_id` UUID; public/customer APIs lookup and serialize by `public_id` only.
- **BREAKING (phased):** Customer/order/address/delivery APIs switch path and payload identity from integer `id` to `public_id` / `*_public_id` reference fields.
- Phase customer-facing live surfaces first (`Order`, `OrderDelivery`, `CustomerAddress`), then optionally admin meal-ops resources (`Ingredient`, `MealCycle`, `MealCyclePlan`, schedules), then stub domains (`wallet`, `payments`, `delivery`, `promotions`, `notifications`) when those APIs are wired.
- Shared migration recipe: nullable add → backfill → unique non-null; never delete/recreate rows.
- Frontend/backend docs per phase so mobile/web clients can migrate in lockstep.
- **Out of immediate scope for URL breaks:** Django `User` PK, singleton settings models, and purely internal admin FK filters (may keep integer until that surface is public).

## Capabilities

### New Capabilities
- `public-uuid-convention`: Shared rules for `public_id` fields, serializer/lookup policy (customer vs admin), migration/backfill, and naming of nested `*_public_id` references.
- `order-public-identifiers`: UUID public IDs for `Order` and `OrderDelivery` on customer and web order APIs (list/detail/cancel/meal-off/mark-delivery/today-board references).
- `customer-address-public-identifiers`: UUID public IDs for `CustomerAddress` (and any customer profile nested address identity exposed to clients).
- `ops-catalog-public-identifiers`: Optional later phase for admin meal-ops resources (`Ingredient`, `MealCycle`, `MealCyclePlan`, `MealCyclePlanLine`, `MonthlyMenuSchedule`) so manager UIs can also stop relying on sequential IDs in URLs.
- `deferred-domain-public-uuids`: Convention + readiness checklist for stub apps (`wallet`, `payments`, `delivery`, `promotions`, `notifications`) so new endpoints ship UUID-first.

### Modified Capabilities
- (none in `openspec/specs/` — meal public UUID already lives under change `meal-public-uuid`; this plan extends the same pattern project-wide)

## Impact

- **Already done:** `MealCategory.public_id`; order create `meal_public_id`; today-menu meal identity.
- **Live wired apps (`core/urls.py`):** `orders`, `meals` (remaining integer IDs), `user_management` (addresses/profile ids).
- **Stub apps (models/ViewSets exist, not mounted in root urls yet):** `wallet`, `payments`, `delivery`, `promotions`, `notifications`, `business`.
- **Clients:** All storefront/mobile flows using order/delivery/address integer IDs; admin web boards using order/delivery PKs in paths.
- **Risk:** Coordinated multi-phase breaking releases; docs and OpenAPI must ship with each phase.
