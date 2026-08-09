## 1. Pre-release verification (local)

- [x] 1.1 Confirm `service_area` is in `INSTALLED_APPS` and both URL includes exist in `core/urls.py`
- [x] 1.2 Run `python manage.py test service_area.tests.test_service_area` and ensure all tests pass
- [x] 1.3 Run `python manage.py showmigrations service_area` and confirm `0001_initial` is the expected migration to ship
- [x] 1.4 Diff against `origin/main` and list every file that must be in the release commit (`service_area/**`, `core/urls.py`, `core/settings/base.py`, `core/settings/local.py`, `orders/services/order_service.py`, `orders/api/serializers.py`, docs)

## 2. Ship backend to production

- [ ] 2.1 Create a single release commit (when user asks) that includes the service-area app + wiring; exclude `db.sqlite3`, secrets, and `__pycache__`
- [ ] 2.2 Push to the deploy branch and wait for Render (or target host) to finish the deploy
- [ ] 2.3 Apply migrations on production (`python manage.py migrate service_area` or full `migrate`)
- [ ] 2.4 Set Render env `SERVICE_AREA_ORDER_GATE_ENABLED=False` for the initial cutover window

## 3. Production smoke checks

- [ ] 3.1 Probe `GET /api/v1/web/service-areas/` — must not be Django unmatched-route HTML 404 (401/403 without admin token is acceptable)
- [ ] 3.2 Probe `POST /api/v1/service-areas/check/` with valid lat/lng JSON — must not be URL 404
- [ ] 3.3 As verified admin, create at least one active hub via `POST /api/v1/web/service-areas/`
- [ ] 3.4 Re-check with an in-radius point → `service_available=true`; out-of-radius → nearest hub + false
- [ ] 3.5 Confirm `GET .../requests/` and `.../requests/summary/` resolve for admin

## 4. Order gate cutover

- [x] 4.1 Confirm customer delivery places used at checkout can store/send latitude & longitude
- [ ] 4.2 Flip `SERVICE_AREA_ORDER_GATE_ENABLED=True` on production after hubs exist
- [ ] 4.3 Verify in-radius order create succeeds (other order rules permitting)
- [ ] 4.4 Verify out-of-radius / missing-coords order create returns `SERVICE_AREA_UNAVAILABLE` / `DELIVERY_LOCATION_REQUIRED`
- [x] 4.5 Document rollback: set gate `False` immediately if checkout regressions appear

## 5. Frontend cutover plan execution (client repos)

- [ ] 5.1 Admin: wire Service Areas module to `/api/v1/web/service-areas/` per `service_area/docs/frontend/admin-service-areas.md` (list/create/edit/status/analytics)
- [ ] 5.2 Admin: map picker UX (marker + radius circle); treat HTML/non-JSON 404 as API outage, not empty data
- [ ] 5.3 Customer: Delivery box → geolocation/map → `POST /api/v1/service-areas/check/`; guest header `X-Guest-Session-Id`
- [ ] 5.4 Customer: demand CTA → `POST /api/v1/service-areas/demand/`; never unlock checkout from demand alone
- [ ] 5.5 Customer: on order create, handle `DELIVERY_LOCATION_REQUIRED` and `SERVICE_AREA_UNAVAILABLE` with Bangla copy and return to location selection
- [ ] 5.6 Ensure delivery place save path persists lat/lng before package order create

## 6. Docs & closeout

- [x] 6.1 Spot-check `service_area/docs/backend/service-area-verification.md` and frontend docs against live production paths
- [x] 6.2 Add a short “Production release checklist” note to backend docs if any env/migrate step was missing
- [ ] 6.3 Record cutover completion (gate enabled date, first hub public_id) for ops handoff
