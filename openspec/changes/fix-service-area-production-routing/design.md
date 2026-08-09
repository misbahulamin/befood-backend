## Context

Local workspace already contains a complete `service_area` implementation from change `location-based-service-area-verification` (23/23 tests green). Production Render URL conf (2026-08-10) does **not** include any `service-areas` routes; Django debug 404 lists only inventory/admin-wallet/onahar/etc.

Git audit:

| Path | Local state vs `origin/main` |
|------|------------------------------|
| `service_area/` | **Untracked** — never committed |
| `core/urls.py` | Modified (+2 includes) — uncommitted |
| `core/settings/base.py` | Modified (`INSTALLED_APPS` + settings) — uncommitted |
| `core/settings/local.py` | Modified (test gate off) — uncommitted |
| `orders/services/order_service.py` | Modified (order gate) — uncommitted |
| `orders/api/serializers.py` | Modified (`ServiceAreaOrderError`) — uncommitted |

Production probes:

- `GET /api/v1/web/service-areas/` → **404**
- `POST /api/v1/service-areas/check/` → **404**

This is not a serializer/permission bug; the routes are absent from the deployed codebase.

### Backend error audit (beyond the reported 404)

1. **P0 — Routes missing on production**  
   Root cause: feature not committed/pushed/deployed. Local wiring is correct.

2. **P0 — Migrations not applied on production**  
   After first deploy, `service_area.0001_initial` MUST run or admin/check endpoints 500 on table-missing.

3. **P1 — Order gate default ON after deploy**  
   `SERVICE_AREA_ORDER_GATE_ENABLED` defaults `True`. With zero hubs or delivery places without lat/lng, meal-order create fails with `SERVICE_AREA_UNAVAILABLE` / `DELIVERY_LOCATION_REQUIRED`. Local tests disable the gate; production will not.

4. **P1 — Delivery places may lack coordinates**  
   `CustomerDeliveryPlace.latitude/longitude` are nullable. Gate requires coords for resolved lunch/dinner places. Existing customers who only have address text will be blocked until FE/admin collects map pins.

5. **P2 — Empty active hub set**  
   Matching returns `service_available=false` for every check until admins create active hubs. Demand still works.

6. **Not a backend defect (local)**  
   Logic, Haversine matching, admin CRUD, analytics filters, OpenAPI helpers, and docs under `service_area/docs/` are already implemented and tested. No additional domain redesign required for this change.

7. **Out of scope findings (do not fix here)**  
   `core/settings/base.py` contains a plaintext email password (pre-existing secret hygiene issue). Inventory `__init__.py` touch-files are unrelated.

### Frontend impact snapshot

- Admin FE already targeting `/api/v1/web/service-areas/` (matches docs) — fails only because backend is undeployed.
- Customer FE must use `/api/v1/service-areas/check|demand/` with GPS/map coords (not IP, not area-name string matching).
- Order create clients must surface `error_code` values `DELIVERY_LOCATION_REQUIRED` and `SERVICE_AREA_UNAVAILABLE` from validation errors.

## Goals / Non-Goals

**Goals:**

- Ship the existing service-area backend to production with migrations.
- Verify public + web routes resolve (no Django “Page not found” URL miss).
- Cut over the order gate safely (hubs + coords readiness).
- Give frontend a concrete adjustment plan so admin/customer UIs work against the live API.

**Non-Goals:**

- Redesigning matching algorithm, models, or URL paths.
- Building the admin/customer frontend in this repo.
- Syncing main OpenSpec specs archive for the prior change (optional later).
- Fixing unrelated secret hygiene in settings.

## Decisions

1. **Ship existing implementation as-is; do not rename routes**  
   - Rationale: FE and docs already use `/api/v1/service-areas/` and `/api/v1/web/service-areas/`. Renaming would create a second 404 class of bugs.  
   - Alternative considered: temporary alias under `orders/` — rejected; multi-client convention already uses dedicated app mounts.

2. **Release sequence: commit → deploy → migrate → seed hubs → enable gate**  
   - Rationale: prevents order-create outage between deploy and hub setup.  
   - Alternative considered: leave gate default True and hope — rejected; production has no hubs yet.

3. **Prefer env override for gate during cutover**  
   - Set `SERVICE_AREA_ORDER_GATE_ENABLED=False` on Render until at least one active hub exists and delivery-place coordinate UX is live; then set `True`.  
   - Alternative considered: code change to default False in production settings — rejected; product intent is gate-on; env is the reversible knob.

4. **Frontend plan lives as capability + tasks, not new backend APIs**  
   - Docs already exist at `service_area/docs/frontend/`. This change adds cutover checklist requirements and any small doc clarifications discovered during release QA.

5. **Verification = route resolve + auth + one happy-path check**  
   - After deploy: admin list must not 404 (401/403 without token is OK); check with body coords must not 404 (200/422 OK).

## Risks / Trade-offs

- **[Risk] Deploy without migrate → 500s** → Mitigation: Render release command / post-deploy `python manage.py migrate`; smoke after migrate.
- **[Risk] Gate on + empty hubs → all package orders fail** → Mitigation: env gate off until hubs seeded; admin create hub first.
- **[Risk] Customers without lat/lng on delivery places → order rejects** → Mitigation: FE forces map/GPS before checkout; show Bangla copy for `DELIVERY_LOCATION_REQUIRED`.
- **[Risk] Partial commit (urls without app)** → Mitigation: single release commit including `service_area/` + wiring + order hooks.
- **[Trade-off] Soft gate delay** → Brief period where checkout is not geo-enforced; accepted for safe rollout.

## Migration Plan

1. Commit all `service_area` sources + `core`/`orders` wiring (exclude `db.sqlite3`, secrets, `__pycache__`).
2. Push to the branch Render deploys from (`main` or agreed release branch).
3. Deploy; confirm process restarts.
4. Run migrations (`service_area.0001_initial`).
5. Keep `SERVICE_AREA_ORDER_GATE_ENABLED=False` until step 7.
6. Admin creates ≥1 active hub via `/api/v1/web/service-areas/`.
7. Confirm customer check API returns `service_available` for an in-radius point.
8. Enable order gate (`True`); retest order create in/out of radius.
9. Rollback: redeploy previous commit and/or set gate `False`. Tables can remain (no destructive migration).

## Frontend adjustment plan (for client repos)

### Admin (`befood` admin panel)

1. Base URL: `{API}/api/v1/web/service-areas/` with `Authorization: Token <admin>`.
2. List: `GET ?page=&page_size=&is_active=&q=` — stop treating HTML 404 as empty list; show “API unavailable” if non-JSON 404.
3. Create/Edit: Google Map click → lat/lng + radius circle preview; POST/PATCH body per docs.
4. Status toggle: `POST .../{public_id}/status/` with `{"is_active": true|false}`.
5. Analytics: map `requests/summary` → Top requests / Top non-serviceable panels.
6. After backend ships: create production hubs before asking customers to verify.

### Customer web (`befood_frontend`)

1. Delivery box: browser geolocation → `POST /api/v1/service-areas/check/` (never IP).
2. Persist `X-Guest-Session-Id` for guests.
3. UI states from `service_available`, `location_reliable`, `nearest_service_area`, `distance_km`.
4. Demand CTA → `POST /api/v1/service-areas/demand/`.
5. Ensure delivery places saved with latitude/longitude before order create.
6. On order create validation: handle `DELIVERY_LOCATION_REQUIRED` and `SERVICE_AREA_UNAVAILABLE` (read `error_code` from serializer error payload).
7. Do not locally compute “inside radius” as checkout authority.

## Open Questions

- Which Render release command currently runs migrations (build vs start)? Confirm before merge.
- Who seeds the first production hub coordinates (ops vs admin user)?
- Exact date to flip `SERVICE_AREA_ORDER_GATE_ENABLED=True` after FE delivery-place map work lands.
