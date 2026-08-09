## Context

DevTools shows two XHR calls during Delivery location verification:

1. Nominatim `reverse?format=jsonv2&lat=…&lon=…` — free OSM geocoder (succeeds).
2. BeFood `…/api/v1/service-areas/check/` — returns `{"detail":"Invalid token."}` (fails).

Backend view already has `permission_classes = [AllowAny]`. Global DRF setting still uses `TokenAuthentication`. In DRF, **an invalid `Authorization` header fails authentication with 401 even when permission is AllowAny**. Missing Authorization → anonymous → allowed. Present-but-invalid Authorization → 401.

Frontend (`F:\befood\befood-frontend`):

- `serviceAreasApi.ts` posts via `apiClient`.
- `apiClient` interceptor always sets `Authorization: Token ${authToken.get()}` when any string exists in `localStorage`.
- Stale/wrong-env/deleted-server tokens therefore break guest check.
- Public content APIs already use `createPublicApiClient()` which strips Authorization — service-area check/demand do not.

Map stack is already free: Leaflet + OSM tiles + Nominatim. No Google/Mapbox billing path is required for this bug.

## Goals / Non-Goals

**Goals:**

- Guests with no login can complete check/demand.
- Users with a stale customer token can still complete check/demand (recover).
- Logged-in customers with a **valid** token still attach identity so history stores `customer_profile`.
- Keep free geocoding/maps (Nominatim/OSM/Leaflet).
- Document the failure mode so FE/QA do not chase map API keys.

**Non-Goals:**

- Replacing Nominatim with a paid geocoder.
- Changing admin `/api/v1/web/service-areas/` auth.
- Fixing unrelated production deploy 404 for undeployed routes (separate change `fix-service-area-production-routing`).
- Broad rewrite of all `apiClient` 401 handling beyond what check/demand needs (optional small shared helper OK).

## Decisions

1. **Primary fix in frontend client policy**  
   - For check/demand: if customer is not authenticated (no session / no token), use a public client (no Authorization) + `X-Guest-Session-Id`.  
   - If authenticated with a token, send `Authorization: Token …` so backend can attach `customer_profile`.  
   - If response is 401 with invalid/expired token detail: remove stale `authToken`, retry **once** without Authorization (guest path).  
   - Rationale: matches notices/blogs pattern; fixes the observed DevTools failure without waiting on backend deploy.  
   - Alternative: only backend OptionalTokenAuthentication — rejected as sole fix because FE would keep sending bad tokens and other AllowAny endpoints could still surprise clients; do both if cheap.

2. **Backend defense-in-depth: OptionalTokenAuthentication on check/demand**  
   - Custom authentication class: valid token → user; missing/invalid token → `None` (no exception).  
   - Apply only to `ServiceAreaCheckView` / `ServiceAreaDemandView`.  
   - Rationale: protects guests even if another client sends a junk header.  
   - Alternative: change global DRF auth — rejected (too wide).

3. **Keep Nominatim / Leaflet as default**  
   - Confirm docs say free OSM stack; `Invalid token` is BeFood auth, not Nominatim.  
   - Alternative: switch to Google Geocoding — rejected per product (no paid map).

4. **Do not treat map outage as auth error**  
   - Reverse geocode failure → proceed with `location_name: null` (already acceptable). Check API failure messaging stays distinct from Nominatim failures.

## Risks / Trade-offs

- **[Risk] Clearing token on any 401 clears a still-valid session for other reasons** → Mitigation: only clear+retry when detail indicates invalid/expired token (or check/demand-specific 401), then retry once without auth.
- **[Risk] Logged-in user with briefly invalid token loses session silently** → Mitigation: clear token + optional toast “session expired”; guest check still works; user can re-login for order create.
- **[Risk] Backend optional auth alone not deployed yet** → Mitigation: FE fix is sufficient for local/prod once FE ships; BE is additive.
- **[Trade-off] Dual FE+BE fix** → Slightly more work; much more robust for guests.

## Migration Plan

1. Implement FE `serviceAreasApi` token policy + one-shot retry.
2. Add BE optional token auth + tests (`invalid token` → 200 guest path).
3. Update `customer-service-area.md` auth section.
4. Manual QA: empty localStorage → check OK; plant garbage token → check OK after clear/retry; valid login → check stores customer.
5. Rollback: revert FE client change; BE optional auth is backward compatible.

## Open Questions

- Should stale-token clear also reset customer auth UI store (Zustand/context), or only `localStorage` token key? Prefer clearing the same `authToken` helper the rest of the app uses so UI re-renders as logged out.
- Exact Bangla/English copy for “session expired, continuing as guest” toast — product can tweak later.
