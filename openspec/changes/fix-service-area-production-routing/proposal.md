## Why

Production (`befood-backend.onrender.com`) returns Django 404 for `GET /api/v1/web/service-areas/` and `POST /api/v1/service-areas/check/` because the completed `service_area` feature exists only in the local working tree and was never committed or deployed to `origin/main`. Admin and customer frontends that already call these documented paths fail until the backend release lands, and checkout must stay safe during the cutover.

## What Changes

- Commit and deploy the untracked `service_area` app plus wiring in `core/urls.py`, `INSTALLED_APPS`, settings flags, and order-create gate hooks.
- Run `service_area` migrations on production after deploy.
- Add a deploy verification checklist (route presence, migration, smoke checks) so URL registration regressions are caught before frontend QA.
- Document a controlled cutover for `SERVICE_AREA_ORDER_GATE_ENABLED` so live order create is not hard-blocked when no hubs or delivery coordinates exist yet.
- Publish a frontend integration / adjustment plan for admin and customer clients so they call the correct contracts and handle post-deploy error codes.
- No new domain API surface beyond what `location-based-service-area-verification` already defined; this change ships and hardens that work for production.

## Capabilities

### New Capabilities

- `service-area-production-release`: Ensure service-area public and web admin routes, migrations, and settings are present and verifiable on production after release.
- `service-area-order-gate-cutover`: Controlled enablement of the order-create service-area gate so production checkout fails only when hubs and delivery coordinates are ready.
- `service-area-frontend-cutover`: Frontend adjustments for admin hub management and customer delivery-box / checkout error handling against the released API contracts.

### Modified Capabilities

- (none — main `openspec/specs/` has no published service-area capability to delta yet; behavior remains as defined by the completed change `location-based-service-area-verification`)

## Impact

- **Backend code (local, unpushed today):** `service_area/` (models, API, services, migrations, tests, docs), `core/urls.py`, `core/settings/base.py`, `core/settings/local.py`, `orders/services/order_service.py`, `orders/api/serializers.py`
- **APIs that must appear on production after deploy:**
  - `POST /api/v1/service-areas/check/`
  - `POST /api/v1/service-areas/demand/`
  - `GET|POST /api/v1/web/service-areas/`
  - `GET|PATCH|DELETE /api/v1/web/service-areas/{public_id}/`
  - `POST /api/v1/web/service-areas/{public_id}/status/`
  - `GET /api/v1/web/service-areas/requests/`
  - `GET /api/v1/web/service-areas/requests/summary/`
- **Runtime:** Render deploy + `migrate`; optional env `SERVICE_AREA_ORDER_GATE_ENABLED`, `SERVICE_AREA_ACCURACY_THRESHOLD_M`
- **Clients:** Admin panel hub CRUD/analytics; customer web delivery box + order create error handling
- **Risk if gate is left on with empty hubs / null delivery lat-lng:** order create returns `SERVICE_AREA_UNAVAILABLE` or `DELIVERY_LOCATION_REQUIRED`
