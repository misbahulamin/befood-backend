# Tasks

## 1. Wire ops helpers into the web view

- [x] 1.1 In `delivery_zones/api/web_views.py`, import `parse_ops_query` and `build_ops_summary` from `delivery_zones.services.ops` at module level and verify the file has no undefined references to either symbol (import both in one edit so the second `NameError` cannot remain)
- [x] 1.2 Confirm `DeliveryZoneOpsSummaryView.get` still catches `DeliveryZoneError` via `_error_response` and returns `Response(payload)` on success — verify by reading the method after the import change

## 2. Verify regression coverage

- [x] 2.1 Run the existing zone-based delivery test that hits `GET /api/v1/web/delivery-zones/ops/summary/` (in `delivery_zones/tests/test_zone_based_delivery.py`) and verify it returns HTTP 200 with `unassigned_location_count` (or equivalent asserted fields) instead of raising `NameError`
- [x] 2.2 Manually or via curl/httpx call `GET /api/v1/web/delivery-zones/ops/summary/?service_date=<today>&meal_period=lunch` as a verified admin and verify JSON 200; then reload `/admin/delivery-zones` and verify the ops section no longer shows Django DEBUG HTML

## Workflow follow-up

- Archive the change after review when the ops summary endpoint is confirmed healthy in local admin.
- Optional separate frontend change: harden `getApiErrorMessage` so string HTML/DEBUG bodies are not rendered verbatim in admin UI.
