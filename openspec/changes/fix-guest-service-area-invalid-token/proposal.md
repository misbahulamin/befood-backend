## Why

Guests (and users with a stale customer token in `localStorage`) cannot complete Delivery location check: `POST /api/v1/service-areas/check/` returns `{"detail":"Invalid token."}` even though the endpoint is `AllowAny`. The free Nominatim reverse-geocode call succeeds; the failure is auth header handling on the BeFood check request. Unauthenticated users must be able to verify coverage without logging in.

## What Changes

- Fix the customer frontend service-area API client so check/demand do not send a bad `Authorization: Token …` header for guests; attach a token only for a real logged-in customer session, matching the existing `createPublicApiClient` pattern used by notices/FAQs/blogs.
- On `401` with invalid/expired token during check/demand, clear the stale customer token (or retry once without Authorization) so the guest flow still succeeds.
- Optionally harden the backend check/demand views with optional token authentication that ignores invalid credentials (treat as anonymous) while still attaching `customer_profile` when the token is valid.
- Update frontend docs to state: guest check must work without login; free OSM/Nominatim/Leaflet stack is intentional; `Invalid token` is not a map-API failure.
- No paid map provider is introduced.

## Capabilities

### New Capabilities

- `guest-service-area-check-auth`: Guest-accessible service-area check/demand must succeed without a valid auth token; invalid Authorization must not block coverage verification.
- `service-area-check-client-token-policy`: Frontend client policy for when to send `Authorization` vs guest headers on check/demand, including stale-token recovery.

### Modified Capabilities

- (none in `openspec/specs/` — service-area guest auth was never archived to main specs)

## Impact

- **Root cause (confirmed):** `befood-frontend` `src/features/service-area/api/serviceAreasApi.ts` uses `apiClient`, which always attaches `authToken` from `localStorage`. DRF global `TokenAuthentication` rejects invalid tokens with 401 **before** `AllowAny` applies.
- **Not the cause:** Free Nominatim (`nominatim.openstreetmap.org/reverse`) / Leaflet OSM tiles — those requests succeed independently and do not produce `Invalid token`.
- **Frontend:** `F:\befood\befood-frontend` — `serviceAreasApi.ts`, possibly `apiClient` 401 handling, guest session headers, docs under backend `service_area/docs/frontend/customer-service-area.md`.
- **Backend (optional defense-in-depth):** `service_area/api/views.py` authentication_classes for check/demand; tests for invalid-token-as-guest.
- **Admin web service-areas** unchanged (still require verified admin token).
