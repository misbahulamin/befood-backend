## Why

BeFood already generates lunch/dinner `OrderDelivery` slots and has Delivery Man accounts, but operations still lack a manual neighborhood grouping model. Without GPS-based routing yet, admins need Zone → Location → Customer assignment and zone-scoped Delivery Man boards so daily meal delivery can be planned by priority instead of flat address lists.

## What Changes

- Introduce operational **Delivery Zones** (named areas with priority and optional assigned Delivery Man), separate from existing GPS `ServiceArea` coverage hubs and unused `business.DeliveryZone` fee circles.
- Introduce operational **Delivery Locations** (e.g. Chawkbazar, DC Road) that belong to exactly one Zone, each with its own delivery priority for stop ordering.
- Add **manual customer → Location assignment**; customer Zone is always derived from Location (no direct customer↔zone FK). Moving a Location to another Zone automatically moves all assigned customers.
- Assign **one primary Delivery Man per Zone** in phase 1 (schema ready for multiple riders later).
- Extend admin customer and deliveryman APIs to assign/view Location and Zone.
- Add admin ops views: zone-wise / location-wise delivery counts and Delivery Man workload for a service date + meal period.
- Add Delivery Man **today board** scoped to their assigned Zone, grouped by Location priority for lunch and dinner.
- Document admin and deliveryman frontend contracts; keep customer GPS address book (`CustomerDeliveryPlace`) unchanged as the street-level destination.
- Design for future Google Maps / GPS auto-zone detection / multi-rider workload without rewriting the Zone→Location hierarchy.

## Capabilities

### New Capabilities

- `delivery-zone-management`: Admin CRUD for operational zones (name, code, priority, status, primary Delivery Man assignment).
- `delivery-location-management`: Admin CRUD for named locations inside a zone, location priority, and safe zone reassignment with cascading customer zone membership.
- `customer-zone-assignment`: Manual customer→location assignment; derived zone exposure; rules when location is inactive/moved/deleted.
- `deliveryman-zone-scope`: Bind Delivery Man to a zone; enforce that a deliveryman only sees deliveries in their assigned zone.
- `deliveryman-delivery-board`: Zone-scoped lunch/dinner delivery board with totals, location-priority grouping, customer list, and address display.
- `admin-zone-delivery-ops`: Admin zone/location delivery counts and Delivery Man workload for planning.
- `zone-delivery-frontend-docs`: Frontend-facing docs for admin zone/location/customer assignment UIs and deliveryman board.

### Modified Capabilities

- `admin-customer-directory`: Customer list/detail MUST expose assigned location, derived zone, and allow admin location assignment/change.
- `deliveryman-admin-management`: Deliveryman admin detail MUST expose assigned zone and support zone assignment.
- `admin-order-management`: Today-board (or equivalent admin delivery list) MUST support optional zone/location/deliveryman filters and aggregated counts without breaking existing date/meal_period/status filters.

## Impact

- **Apps:** New or extended app surface (preferred: dedicated `delivery_zones` app, or a clear module under `delivery`/`orders`); touch `user_management` (CustomerProfile + RiderProfile FKs), `orders` (board queries / serializers), possibly thin `delivery` scaffolding retirement for this use case.
- **Do not conflate:** `service_area.ServiceArea` remains GPS coverage gate; `business.DeliveryZone` remains unused fee scaffold — neither becomes the operational Zone.
- **APIs:** New `/api/v1/web/delivery-zones/`, `/api/v1/web/delivery-locations/`, admin ops endpoints; deliveryman board under deliveryman-auth paths; OpenAPI + frontend docs required.
- **Auth:** `IsVerifiedAdmin` for zone/location/assignment mutations; `IsVerifiedDeliveryman` for rider board (zone-scoped queryset).
- **Data:** Soft-delete / deactivate preferred over hard delete when locations/zones still have customers or scheduled deliveries.
- **Out of scope (phase 1):** Google Maps polygons, GPS auto-assignment, route optimization, multiple simultaneous riders per zone, automatic customer location inference from lat/lng.
