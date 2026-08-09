## 1. Frontend client fix (`F:\befood\befood-frontend`)

- [ ] 1.1 Change `src/features/service-area/api/serviceAreasApi.ts` so check/demand do not use bare `apiClient` auth attachment for guests (use `createPublicApiClient` and/or conditional Authorization)
- [ ] 1.2 When no customer token exists, omit `Authorization` and keep `X-Guest-Session-Id` + `X-Client-Type`
- [ ] 1.3 When a token exists, send it; on `401` Invalid/expired token, clear `authToken` (and auth store if needed) and retry check/demand once without Authorization
- [ ] 1.4 Manual verify in DevTools: empty storage → check `200`; plant garbage Token → recovers; valid login → check still works

## 2. Backend defense-in-depth (`befood-backend`)

- [ ] 2.1 Add optional Token authentication helper that returns anonymous on missing/invalid token (no 401 raise)
- [ ] 2.2 Set `authentication_classes` on `ServiceAreaCheckView` and `ServiceAreaDemandView` to that helper; keep `AllowAny`
- [ ] 2.3 Add API tests: no auth → 200; invalid Token header → 200 guest path; valid Token → history linked to customer
- [ ] 2.4 Run `python manage.py test service_area.tests.test_service_area`

## 3. Docs

- [ ] 3.1 Update `service_area/docs/frontend/customer-service-area.md`: guest check without login; stale-token behavior; clarify `Invalid token` ≠ Nominatim/map failure
- [ ] 3.2 Note free stack remains Leaflet + OSM tiles + Nominatim (no paid map required for this fix)
- [ ] 3.3 Brief note in backend docs permissions section about optional token on check/demand

## 4. QA closeout

- [ ] 4.1 Confirm reverse geocode (Nominatim) failure still allows check with `location_name: null`
- [ ] 4.2 Confirm admin `/api/v1/web/service-areas/` still requires verified admin Token
- [ ] 4.3 Smoke guest Delivery box end-to-end on local (and production after FE deploy)
