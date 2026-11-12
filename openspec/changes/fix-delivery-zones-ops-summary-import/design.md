# Design

## Context

See `proposal.md` for motivation. Observed failure:

- View: `DeliveryZoneOpsSummaryView.get` in `delivery_zones/api/web_views.py`
- Calls `parse_ops_query(...)` then `build_ops_summary(...)`
- Both helpers already live in `delivery_zones/services/ops.py`
- Neither symbol is imported in `web_views.py`, so the first call raises `NameError`
- Fixing only `parse_ops_query` would immediately raise a second `NameError` on `build_ops_summary`
- Frontend `getApiErrorMessage` returns string response bodies unchanged; Django DEBUG HTML therefore appears as the red wall on `/admin/delivery-zones`
- Existing API coverage in `delivery_zones/tests/test_zone_based_delivery.py` already `GET`s `/api/v1/web/delivery-zones/ops/summary/` and expects 200 — that test should fail today and pass after the import fix

Static check of `delivery_zones` API modules: no other call sites for these two helpers outside this view (tests import `build_ops_summary` directly).

## Goals / Non-Goals

**Goals:**

- Restore the ops summary endpoint with the smallest correct wiring change
- Catch the latent second missing symbol in the same edit
- Prove the fix via the existing HTTP test (and optionally a quick live GET)

**Non-Goals:**

- Changing ops summary payload shape, filters, or business counting rules
- Frontend HTML/500 message sanitization in `getApiErrorMessage` (optional follow-up in `befood-frontend`)
- Broader import linting / CI NameError scanning across the monorepo
- Re-architecting zone ops services or OpenAPI schemas beyond what is already documented

## Decisions

1. **Import both helpers from `delivery_zones.services.ops` into `web_views.py`**
   - Rationale: helpers already exist and match the view’s intended thin-controller pattern (parse → service → Response).
   - Alternative considered: inline query parsing in the view — rejected; duplicates `parse_ops_query` allowlist/validation and drifts from service layering.
   - Alternative considered: lazy import inside `get` — rejected; normal module-level import is clearer and matches the rest of the file.

2. **Keep response/error mapping unchanged**
   - Continue catching `DeliveryZoneError` via `_error_response`.
   - No new error codes or status mapping for this fix.

3. **Verification via existing test, not new fixture sprawl**
   - Prefer running the existing zone-based delivery test path that already hits the HTTP endpoint.
   - Add a new test only if the existing case is too entangled to run focused and still leave a regression gap.

4. **Frontend remains out of backend change scope**
   - After backend returns JSON, Admin Delivery Zones ops cards should work with current frontend code.
   - Document the HTML dump as DEBUG-only UX noise for a possible separate frontend change.

## Risks / Trade-offs

- **[Risk] Import fixed but ops service still raises for empty/odd data** → Mitigation: re-run API test with seeded deliveries; manual check with same query as the failing browser request (`service_date=2026-11-12&meal_period=lunch`).
- **[Risk] Autoreloader not picking up the change** → Mitigation: confirm process reload or restart `runserver` after edit.
- **[Trade-off] Skipping frontend error sanitization** → Admins still see ugly HTML if another DEBUG 500 occurs; acceptable for this focused backend fix.

## Migration Plan

1. Land the import fix on backend.
2. Restart/reload Django if needed.
3. Confirm `GET /api/v1/web/delivery-zones/ops/summary/?service_date=...&meal_period=lunch` returns 200 JSON.
4. Reload `/admin/delivery-zones` — ops section should show cards or empty-state copy, not red HTML.
5. Rollback: revert the import change (single-file).

## Open Questions

None — root cause and fix path are confirmed from traceback + source.
