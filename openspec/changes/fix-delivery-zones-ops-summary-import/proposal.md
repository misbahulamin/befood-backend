# Proposal

## Why

Admin Delivery Zones (`/admin/delivery-zones`) fails when loading ops summary: `GET /api/v1/web/delivery-zones/ops/summary/` raises `NameError: name 'parse_ops_query' is not defined`. The page shows Django DEBUG HTML in red because the frontend surfaces string error bodies as-is. Ops planning for a service date/meal period is currently unusable.

## What Changes

- Wire `DeliveryZoneOpsSummaryView` to the existing ops service helpers (`parse_ops_query`, `build_ops_summary`) so the endpoint returns JSON instead of 500.
- Confirm no second latent `NameError` remains on the same code path after the first import is fixed.
- Re-run the existing zone-based delivery API test that hits `/ops/summary/` so the regression cannot silently return.
- Document that frontend HTML dump is a DEBUG-side effect of `getApiErrorMessage` (string bodies), not a separate root cause; frontend contract changes are out of scope unless a follow-up is requested.

## Capabilities

### New Capabilities

- `admin-zone-delivery-ops`: Verified-admin zone ops summary HTTP endpoint for `service_date` + `meal_period` (counts and Delivery Man workload) must succeed with JSON when query params are valid.

### Modified Capabilities

- (none — main `openspec/specs/` has no synced `admin-zone-delivery-ops` capability yet; this change introduces a focused delta for the broken endpoint.)

## Impact

- **Backend:** `delivery_zones/api/web_views.py` (missing imports from `delivery_zones.services.ops`); existing tests in `delivery_zones/tests/test_zone_based_delivery.py`.
- **API:** `GET /api/v1/web/delivery-zones/ops/summary/` — no contract change; restore intended 200 JSON behavior.
- **Frontend:** No required code change for the 500 itself. Admin page already calls the endpoint; after the backend fix it should render summary cards again. Optional UX hardening for HTML/500 bodies remains a separate frontend change.
- **Other apps:** Static scan of `delivery_zones` API modules did not find additional undefined `parse_ops_query` / `build_ops_summary` call sites outside this view.
