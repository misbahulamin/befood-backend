# Proposal

## Why

Operational routing today is **Zone → Location → Customer**. One location (for example Chawkbazar) now needs multiple delivery stops, so customers that share a location must be split across finer units. Without **sub-locations**, riders and admins cannot order or assign work inside the same neighborhood without inventing duplicate locations or losing cascade-safe zone membership.

## What Changes

- Introduce **DeliverySubLocation** under each `DeliveryLocation`: name, priority (per parent location), status, `public_id`, optional future geo hooks.
- Move customer operational assignment from **location** to **sub-location**. Customer **location** and **zone** remain **derived** (sub-location → location → zone), including cascade when a location moves zones or a sub-location moves between locations.
- Admin APIs: CRUD + reorder for sub-locations; customer assign/clear via `delivery_sub_location_public_id`; list/detail/filters expose nested zone/location/sub-location.
- Deliveryman today-board and admin ops summary group/count by **location then sub-location** (priority order).
- **Production-safe expand–contract** on AWS: additive schema + backfill default sub-location per existing location, dual-read/compat for old location-assign clients, then cut over; no hard cut that blanks customer routing mid-meal.
- Frontend contract docs for Admin Panel `http://127.0.0.1:5173/admin/delivery-zones` (and customer assignment) so the UI can create Zone / Location / Sub-location and assign customers without breaking live ops.
- **BREAKING (phased):** After the compatibility window, assigning customers by `delivery_location_public_id` alone is removed; clients MUST assign a sub-location. Board/ops payloads add sub-location fields (additive first, then required in docs).

## Capabilities

### New Capabilities

- `delivery-sub-location-management`: Admin create/list/update/deactivate/delete/reorder of sub-locations under a delivery location, with priority uniqueness and safe delete rules.
- `customer-zone-assignment`: Admin assigns customers to a sub-location; zone and location are derived; unassigned customers stay off deliveryman boards; migration/compat rules for legacy location assignment.
- `deliveryman-delivery-board`: Zone-scoped today board groups and orders deliveries by location priority, then sub-location priority, then stable tie-break.
- `admin-zone-delivery-ops`: Ops summary includes zone, location, and sub-location delivery counts plus unassigned (no sub-location) deliveries.
- `zone-delivery-frontend-docs`: Frontend integration docs for admin delivery-zones hierarchy (zone/location/sub-location) and customer assignment/board contract updates.

### Modified Capabilities

- `admin-customer-directory`: Customer list/detail expose `delivery_sub_location` (and derived location/zone); allowlisted filters include `sub_location_public_id` (and keep/clarify location/zone filters via derivation).

## Impact

- **Apps:** `delivery_zones` (models, services, web APIs, board/ops, tests, docs); `user_management` (`CustomerProfile` FK, admin customer serializers/views/filters); `orders` (optional `logistics_sub_location` attribution on `OrderDelivery`, today-board filters).
- **APIs:** New `/api/v1/web/delivery-sub-locations/` (or nested under locations); extend location/zone payloads with `sub_location_count`; change customer `PATCH …/delivery-location/` (compat) and/or add `…/delivery-sub-location/`; board + ops response shape.
- **Data:** Production migration + backfill on AWS; temporary dual FK/`delivery_location` sync during expand–contract; deploy order coordinated with Admin Panel frontend.
- **Non-goals:** GPS auto-matching; multi-rider per zone; changing `ServiceArea` or street `CustomerDeliveryPlace`; implementing the React Admin Panel inside this backend repo (docs + API contract only).
