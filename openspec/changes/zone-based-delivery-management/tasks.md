## 1. App scaffold and models

- [x] 1.1 Create Django app `delivery_zones` with standard layout (`models`, `api/`, `services/`, `tests/`, `docs/`) and register in `INSTALLED_APPS`
- [x] 1.2 Add `DeliveryZone` model (`PublicIdMixin`, name, unique code, priority, status active/inactive, nullable `assigned_delivery_man` → `RiderProfile`, timestamps, future nullable geo hooks)
- [x] 1.3 Add `DeliveryLocation` model (`PublicIdMixin`, name, FK zone, priority, status, timestamps, future nullable geo hooks) with uniqueness of priority among active locations per zone
- [x] 1.4 Enforce phase-1 rule: a Delivery Man is primary on at most one zone (DB constraint and/or service validation)
- [x] 1.5 Add nullable `CustomerProfile.delivery_location` FK → `DeliveryLocation` (`SET_NULL`)
- [x] 1.6 Generate migrations; register models in Django admin for ops debugging

## 2. Zone and location services

- [x] 2.1 Implement `delivery_zones/services/zones.py` create/update/deactivate/delete-empty + assign/clear Delivery Man with approved-rider checks
- [x] 2.2 Implement `delivery_zones/services/locations.py` create/update/deactivate/delete-empty + move between zones (transactional priority handling)
- [x] 2.3 Implement priority reorder/swap helper to avoid uniqueness conflicts when admins change priorities
- [x] 2.4 Block create/move into inactive zones; block delete when dependents exist (locations/customers)

## 3. Customer assignment and admin customer API

- [x] 3.1 Implement `delivery_zones/services/assignment.py` assign/clear customer location with active-location validation
- [x] 3.2 Extend admin customer serializers to expose location + derived zone summaries
- [x] 3.3 Extend admin customer update/PATCH (or nested assign endpoint) to accept `delivery_location_public_id`
- [x] 3.4 Add filter/search affordance for customers by zone/location on admin customer list when practical

## 4. Admin zone/location web APIs

- [x] 4.1 Mount `/api/v1/web/delivery-zones/` and `/api/v1/web/delivery-locations/` in `core/urls.py`
- [x] 4.2 Implement zone CRUD + assign delivery man endpoints with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination
- [x] 4.3 Implement location CRUD + zone move + priority update endpoints
- [x] 4.4 Add serializers + OpenAPI (`extend_schema`) for all zone/location endpoints

## 5. Deliveryman admin binding

- [x] 5.1 Extend deliveryman admin list/detail serializers with assigned zone summary
- [x] 5.2 Support assign/clear zone from deliveryman admin API and/or zone API consistently with uniqueness rules
- [x] 5.3 Reject assigning non-approved Delivery Men

## 6. Ops summary and today-board filters

- [x] 6.1 Implement `delivery_zones/services/ops.py` aggregation for service_date + meal_period (zone counts, location counts, deliveryman workload, unassigned count)
- [x] 6.2 Add `GET /api/v1/web/delivery-zones/ops/summary/` with allowlisted query validation
- [x] 6.3 Extend admin today-board queryset/serializer filters with optional `zone_public_id`, `location_public_id`, `delivery_man_public_id` without breaking existing filters
- [x] 6.4 Update admin-order OpenAPI for new today-board filters

## 7. Deliveryman today board

- [x] 7.1 Implement `delivery_zones/services/board.py` (or orders service) to load zone-scoped `OrderDelivery` rows joined via customer → delivery_location → zone
- [x] 7.2 Add verified-deliveryman endpoint under `/user_management/deliveryman/...` for lunch/dinner (or combined) board with totals, address snapshots, location name/priority ordering
- [x] 7.3 Enforce empty board when rider has no zone; ignore/reject foreign zone query params
- [x] 7.4 Add OpenAPI for deliveryman board responses

## 8. Documentation

- [x] 8.1 Add `delivery_zones/docs/frontend/zone-based-delivery.md` (admin zone/location/customer assign, cascade rules, ops summary, deliveryman board examples)
- [x] 8.2 Add `delivery_zones/docs/backend/zone-based-delivery.md` (models, derived zone rule, ServiceArea vs DeliveryZone distinction, future GPS hooks, edge cases)
- [x] 8.3 Cross-link from admin customer and deliveryman frontend docs where relevant

## 9. Tests

- [x] 9.1 Model/service tests: zone/location CRUD, priority uniqueness, delete guards, assign/clear rider uniqueness
- [x] 9.2 Cascade tests: moving location zone updates derived zone for all assigned customers without per-customer writes
- [x] 9.3 Customer assignment API tests: assign/change/clear; inactive location rejected; admin serializer fields present
- [x] 9.4 Ops summary tests: zone/location counts, workload, unassigned deliveries
- [x] 9.5 Deliveryman board tests: scoped to zone, priority ordering, lunch vs dinner, no-zone empty, permission denied for customers
- [x] 9.6 Today-board filter tests: zone/location/deliveryman filters; legacy filters still work
- [x] 9.7 Run targeted `delivery_zones`, `user_management`, and `orders` tests; fix failures
