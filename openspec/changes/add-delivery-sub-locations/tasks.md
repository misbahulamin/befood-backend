# Tasks

## 1. Schema expand and backfill

- [x] 1.1 Add `DeliverySubLocation` model (FK to `DeliveryLocation`, name, priority, status, `public_id`, optional geo hooks, unique active priority per location) and register in Django admin; verify `makemigrations` produces a clean migration for `delivery_zones`
- [x] 1.2 Add nullable `CustomerProfile.delivery_sub_location` FK and optional nullable `OrderDelivery.logistics_sub_location` FK; verify migrations depend correctly on the sub-location table
- [x] 1.3 Write data migration that creates one default sub-location per existing location (name = location name, priority 1) and backfills `delivery_sub_location` for every customer with `delivery_location`, keeping `delivery_location` set; verify on a staging DB that assigned-customer count equals pre-migrate location-assigned count and every backfilled sub-location’s parent matches the customer’s location
- [x] 1.4 Add settings flag `DELIVERY_SUB_LOCATION_LEGACY_LOCATION_ASSIGN` defaulting True for Bridge; verify it is readable from Django settings in a small unit test or settings smoke assert

## 2. Sub-location services and admin API

- [x] 2.1 Implement `delivery_zones/services/sub_locations.py` (create/update/move/deactivate/delete-if-empty/reorder) with priority uniqueness and inactive-parent guards; verify service unit tests cover create, duplicate priority reject, move cascade, and delete-with-customers blocked
- [x] 2.2 Update location delete/empty guards to block when any child sub-location has customers; verify existing location-delete tests updated and new case passes
- [x] 2.3 Add serializers, web views, URLs for `/api/v1/web/delivery-sub-locations/` (list/create/detail/update/delete) plus reorder endpoint; verify API tests for 201 create, filter by `location_public_id`, and auth 401/403
- [x] 2.4 Extend zone/location list/detail payloads with `sub_location_count` (or nested summary as documented); verify serializer/API tests assert the new field

## 3. Customer assignment Bridge

- [x] 3.1 Implement `assign_customer_sub_location` / clear in `delivery_zones/services/assignment.py` that sets `delivery_sub_location` and mirrors parent into `delivery_location` while Bridge is active; verify unit tests for assign, clear, inactive reject, and parent/zone derivation helpers
- [x] 3.2 Extend admin customer assign endpoint/serializer to accept `delivery_sub_location_public_id` (primary) and, when legacy flag is True, map `delivery_location_public_id` to that location’s default sub-location; verify API tests for both paths and clear-null
- [x] 3.3 When legacy flag is False, reject location-only assign with a clear validation error; verify API test asserts rejection
- [x] 3.4 Update admin customer serializers to expose `delivery_sub_location` plus derived `delivery_location` / `delivery_zone`; verify list/detail response tests

## 4. Admin customer directory filters

- [x] 4.1 Update `user_management/services/admin_customer.py` allowlist and queryset filters for `sub_location_public_id`, `has_delivery_sub_location`, and location/zone filters via `delivery_sub_location__location` (keeping Bridge-compatible behavior); verify filter tests in `test_admin_customer_management.py`
- [x] 4.2 Update `select_related` paths to include `delivery_sub_location__location__zone`; verify no N+1 regressions in existing customer list tests (or add assertNumQueries guard if already used)

## 5. Board and ops dual-read then sub-location grouping

- [x] 5.1 Update board query helpers to scope by derived zone via `delivery_sub_location__location__zone` (Bridge fallback to `delivery_location__zone` only if sub null), require active sub-location/location for listing after Bridge rules; verify board tests still return zone-scoped deliveries after backfill
- [x] 5.2 Change board response grouping to location → sub-location → customers with priority ordering; verify test asserts Gate A before Gate B under the same location
- [x] 5.3 Update ops summary to include per-sub-location counts and unassigned = missing sub-location; verify ops summary API test asserts new counts
- [x] 5.4 Update admin today-board filters to accept `sub_location_public_id` if the today-board already filters by location; verify filter test or documented skip if endpoint does not exist yet

## 6. Backend docs and regression suite

- [x] 6.1 Update `delivery_zones/docs/backend/zone-based-delivery.md` for hierarchy, assign contract, Bridge/Contract flags, and migration notes; verify doc endpoint paths match mounted URLs
- [x] 6.2 Update OpenAPI helpers for new/changed endpoints and fields; verify schema generation or existing openapi test path still passes for touched operations
- [x] 6.3 Run focused suites `delivery_zones/tests/` and admin customer assignment/filter tests; verify all pass locally

## 7. Frontend contract docs and Admin Panel implementation plan

- [x] 7.1 Update `delivery_zones/docs/frontend/zone-based-delivery.md` with Zone → Location → Sub-location endpoint grid, assign payloads, board nesting examples, ops fields, and Bridge compatibility notes; verify examples use real path prefixes `/api/v1/web/...`
- [x] 7.2 Add an **Admin Panel implementation plan** section in that frontend doc covering `/admin/delivery-zones`: UI tree (zone list → locations → sub-locations), cascade selectors for customer assign, reorder UX, empty/error states, and recommended FE deploy after backend Bridge; verify the section lists concrete API call order for create-zone → create-location → create-sub-location → assign-customer
- [x] 7.3 Update `user_management/docs/frontend/admin-customer-management.md` cross-links and fields for sub-location display/filters/assign; verify links resolve to the zone-based delivery doc

## Workflow follow-up

- After backend Bridge is on staging/AWS and Admin Panel FE is dual-aware, flip `DELIVERY_SUB_LOCATION_LEGACY_LOCATION_ASSIGN` to False (Contract) in a controlled window outside peak meal times.
- Optional later change: remove mirrored `CustomerProfile.delivery_location` FK once all clients are on sub-location assign.
- Archive this OpenSpec change after review requirements are satisfied.
- Frontend code changes live in the Admin Panel repo (not this backend); implement against the updated `zone-based-delivery.md` plan.
