# Tasks

## 1. Geo analytics service core

- [x] 1.1 Add `delivery_zones/services/geo_analytics.py` with allowlisted query parsing (`from`, `to`, optional `meal_period`, optional hierarchy UUIDs), Asia/Dhaka inclusive bounds, max 366 days, and `DeliveryZoneError`/`ValidationError` mapping; verify invalid/missing range unit tests fail closed with `400`-ready codes
- [x] 1.2 Implement customer density + lifecycle splits and unassigned customer bucket by current `delivery_sub_location` hierarchy; verify counts match seeded fixtures per zone/location/sub-location
- [x] 1.3 Implement period churn counts and per-node churn rate (active-at-period-start base, zero-base → rate 0) using current geo attribution; verify location churn concentration scenario against fixtures
- [x] 1.4 Implement period meal volume (scheduled/delivered/skipped/missed/total) preferring `logistics_sub_location` with customer sub-location fallback, plus optional `meal_period` filter; verify lunch-only filter and unassigned delivery count
- [x] 1.5 Attach zone primary delivery-man identity + period workload; build `rankings` (high/low density, highest churn with min base 5, highest delivered volume, unassigned totals) in the same matrix payload; verify ranking exclusion threshold

## 2. Web API + OpenAPI

- [x] 2.1 Add verified-admin `GET /api/v1/web/delivery-zones/analytics/matrix/` view, URL mount, thin serializer/response shaping, and OpenAPI helpers; verify `401`/`403`/`400`/`200` via API tests
- [x] 2.2 Support optional `zone_public_id` / `location_public_id` / `sub_location_public_id` scoping with documented not-found/empty behavior; verify subtree filter returns only the scoped hierarchy
- [x] 2.3 Confirm geo drill-down filters on `/api/v1/web/customers/` (`zone_public_id`, `location_public_id`, `sub_location_public_id`, `has_delivery_sub_location`) still work; verify list filter tests (reuse or extend `test_admin_customer_management`) for analytics deep-links

## 3. Docs

- [x] 3.1 Write `delivery_zones/docs/backend/delivery-geo-analytics.md` (endpoints, fields, attribution rules, errors, how to verify); verify doc paths and examples match the implemented contract
- [x] 3.2 Write/update `delivery_zones/docs/frontend/` geo analytics section: ops/summary vs period matrix, rankings, empty states, drill-down into customers/churn lists; verify a frontend engineer can implement UI from the doc alone
- [x] 3.3 Cross-link from existing `zone-based-delivery.md` frontend/backend docs to the new analytics pages; verify links resolve

## 4. Integration verification

- [x] 4.1 Run focused tests (`delivery_zones` geo analytics + customer geo filter tests) and fix regressions; verify suite passes
- [x] 4.2 Smoke-check day `ops/summary` still unchanged for a sample date/meal; verify existing ops summary test still passes

## Workflow follow-up

- Archive the change after review when implementation is complete.
- Hand the customer the Admin Panel frontend prompt covering geo analytics plus related delivery/churn admin surfaces.
