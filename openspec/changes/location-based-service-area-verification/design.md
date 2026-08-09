## Context

Customers already store delivery places with `latitude` / `longitude` (`user_management`), and order creation snapshots those coordinates onto `OrderDelivery`. `business.DeliveryZone` models outlet-linked radius + delivery fee but is **not** used as a serviceability gate. Checkout does not reject out-of-coverage destinations. There is no Google Maps/geocoding integration in the backend today.

Product needs a full **Location-Based Service Area Verification** loop across:

1. **Customer frontend** — Home delivery box: browser geolocation (not IP), reverse geocode for display, manual search/pin fallbacks, cache, UX states.
2. **Backend** — Hub CRUD, Haversine matching, verification API, request history, checkout revalidation.
3. **Verified Admin frontend** — Manage hubs on a map with radius preview; analytics on demand / non-serviceable traffic.

Stakeholders: customers (guests + logged-in), verified admins, order/checkout flows, future expansion planning.

Constraints:

- Final serviceability decision MUST be server-side; frontend only collects/displays.
- Verification MUST use device/browser coordinates, never IP geolocation.
- Customer readable area name MUST NOT determine serviceability (distance vs hub radius only).
- Business logic in `services/`; thin DRF views; `PublicIdMixin` for public/admin API identities where applicable.
- Admin APIs under `/api/v1/web/...` with verified-admin permissions.
- Decimal-safe geo math (no binary float money patterns; distance may use float intermediate but persist rounded `Decimal` km).
- This OpenSpec repo owns backend implementation + client contract docs; customer/admin UI live in sibling frontends.

## Goals / Non-Goals

**Goals:**

- Dedicated service hubs with name, lat/lng, radius_km, active flag, description.
- Guest-friendly `check` API returning `service_available`, customer location echo, matched or nearest hub, `distance_km`.
- Persist every check (and explicit demand CTA) for analytics.
- Checkout/order create rejects non-serviceable delivery coordinates.
- Admin CRUD + analytics endpoints and frontend docs for map-based hub management.
- Accuracy awareness: unreliable GPS surfaces soft failure UX; checkout still revalidates coordinates present on the delivery destination.

**Non-Goals:**

- Polygon/GIS zones or PostGIS (v1 = point + radius).
- Replacing or merging with `business.DeliveryZone` fee model.
- IP-based location, VPN detection, or fraud scoring beyond accuracy signaling.
- Rider routing / hub auto-assignment for kitchen ops.
- Full Admin analytics product (v1 = allowlisted summary endpoints from request history).
- Implementing the React UIs inside this backend repo (docs/contracts only here).

## Decisions

### 1. New app: `service_area/`
- **Choice:** Create `service_area/` (models, services, api, tests, docs). Mount customer/shared check under `/api/v1/service-areas/` and admin under `/api/v1/web/service-areas/`.
- **Rationale:** Coverage verification + demand history is a bounded context distinct from outlet fee zones and from the customer address book.
- **Alternatives considered:**
  - Extend `business.DeliveryZone` — couples fee to coverage; weak fit for demand history and guest checks.
  - Put only under `user_management` — wrong ownership for admin-managed hubs.

### 2. Models: `ServiceArea` + `ServiceAreaRequest`
- **Choice:**
  - `ServiceArea`: `public_id`, `name`, `latitude`, `longitude`, `radius_km`, `is_active`, `description`, `created_by` (nullable admin), timestamps. Optional future fields (`city`, `priority`) deferred.
  - `ServiceAreaRequest`: `public_id`, nullable `user`/`customer_profile`, `guest_session_id`, `latitude`, `longitude`, `accuracy`, `detected_location_name`, `formatted_address` (optional), FK `matched_service_area` (nullable), `distance_km`, `is_serviceable`, `request_kind` (`check` | `demand`), `requested_at` / `created_at`.
- **Rationale:** Matches product tables; keeps customer display name separate from hub name; supports guest + logged-in analytics.
- **Alternatives considered:** Reuse `DeliveryZone` rows — rejected (fee semantics, outlet FK required).

### 3. Distance algorithm: Haversine in Python service
- **Choice:** Implement Haversine in `service_area/services/geo.py` (Earth radius 6371 km). Compare `distance_km <= radius_km` with Decimal rounding to 3–4 decimal places for API/storage. No PostGIS in v1.
- **Rationale:** Enough accuracy for city-scale 3–5 km hubs; zero infra dependency; easy to unit test.
- **Alternatives considered:** PostGIS / `django.contrib.gis` — better at scale later; deferred. Vincenty — unnecessary complexity for this radius.

### 4. Matching rule across multiple hubs
- **Choice:** Among **active** hubs where `distance <= radius_km`, pick the **nearest** as `matched_service_area`. If none cover, set `service_available=false` and return `nearest_service_area` + `distance_km` (nearest among active hubs by distance). Inactive hubs are ignored for matching.
- **Rationale:** Deterministic, multi-hub ready, supports “nearest hub” UX when unavailable.
- **Alternatives considered:** Prefer highest-priority hub among covering set — deferred until `priority` field exists. Prefer largest radius — less intuitive.

### 5. Verification API contract
- **Choice:** `POST /api/v1/service-areas/check` (AllowAny or authenticated optional). Body: `latitude`, `longitude`, required; `accuracy` optional; `location_name` optional/nullable; optional `guest_session_id` (or `X-Guest-Session-Id`). Always persist a `ServiceAreaRequest` with `request_kind=check`. Response includes `verified`, `service_available`, `customer_location`, `matched_service_area` XOR `nearest_service_area`, `distance_km`, and `location_reliable` (see accuracy).
- **Demand CTA:** `POST /api/v1/service-areas/demand` (or same check with `request_kind` / flag) saves `request_kind=demand` for “আমার এলাকায় BeFood চাই”.
- **Rationale:** Aligns with product examples while fitting `/api/v1/` versioning; guest-friendly.
- **Alternatives considered:** Exact path `/api/service-area/check` without version — rejected for project convention.

### 6. Accuracy handling
- **Choice:** Configurable soft threshold (default **500 meters**). If `accuracy` is present and `> threshold`, response sets `location_reliable=false` and a stable `warning_code` (e.g. `LOW_LOCATION_ACCURACY`); still compute distance for history. If `accuracy` omitted (manual pin/search), treat as reliable for check purposes. Checkout gate requires coordinates; MAY reject when last check for those coords was unreliable **only if** product wiring passes that flag—v1 checkout gate validates **coverage only**, while frontend blocks proceeding on low accuracy until retry/manual pin.
- **Rationale:** Matches product UX without making backend silently invent accuracy.
- **Alternatives considered:** Hard-fail check API on low accuracy — worse for analytics; soft warning preferred.

### 7. Reverse geocoding ownership
- **Choice:** Prefer **client-side** Google reverse geocode for Home UX; backend accepts optional `location_name` / `formatted_address` for history. Optional backend geocode helper deferred unless admin tooling needs it.
- **Rationale:** Keeps Maps key usage on frontends that already embed Maps; backend remains source of truth for distance only.
- **Alternatives considered:** Backend-only geocode on every check — extra latency/cost; can add later.

### 8. Checkout / order-create gate
- **Choice:** In `orders` create path (after delivery place resolution), call `service_area.services.verification.assert_serviceable(lat, lng)`. If missing coordinates or not covered by any active hub → reject with clear `error_code` (e.g. `SERVICE_AREA_UNAVAILABLE` / `DELIVERY_LOCATION_REQUIRED`). Do not trust client `service_available` flags.
- **Rationale:** Product security rule; coordinates already snapshotted today.
- **Alternatives considered:** Gate only Home UI — insecure. Gate address-save only — insufficient for checkout address changes.

### 9. Relationship to `DeliveryZone`
- **Choice:** Leave `business.DeliveryZone` unchanged for fee/outlet concepts. Document that serviceability uses `service_area.ServiceArea` only. Future consolidation is out of scope.
- **Rationale:** Avoid breaking fee rules; clear mental model for admins (“Service Hubs” vs “Delivery fee zones”).

### 10. Admin API shape
- **Choice:** `/api/v1/web/service-areas/` list/create; `/{public_id}/` retrieve/patch/delete; action endpoints for activate/deactivate if not covered by PATCH; analytics `GET .../requests/summary/` (top areas, top non-serviceable) with date filters + pagination on raw request list. Permission: `IsVerifiedAdmin` (+ group codenames if cheap).
- **Rationale:** Mirrors `admin_wallet` / `inventory` web patterns.
- **Alternatives considered:** Django admin only — insufficient for map picker SPA.

### 11. Guest identity
- **Choice:** Client-generated UUID stored in localStorage; sent as `guest_session_id` on check/demand. Logged-in users attach `user`/`customer_profile` and MAY still send guest id for continuity. No PII required for guest checks.
- **Rationale:** Enables demand analytics without forcing login on first Home visit.

### 12. Caching (client contract)
- **Choice:** Document frontend cache of last successful verification (coords, name, hub id, `verified_at`). Re-check when location manually changed, cache older than TTL (e.g. 24h), or at checkout. Backend remains authoritative on every check/checkout.
- **Rationale:** Avoids repeated permission prompts; TTL prevents stale hubs after admin radius changes.

## Risks / Trade-offs

- **[Risk] GPS spoofing / fake coordinates** → Mitigation: server-side gate still required; accuracy warning; future rate limits / device attestation out of scope.
- **[Risk] Low GPS accuracy near hub boundary** → Mitigation: soft `location_reliable` + manual pin; do not hard-block analytics writes.
- **[Risk] Overlap of hubs** → Mitigation: nearest covering hub wins; document in admin UI.
- **[Risk] Confusion with `DeliveryZone`** → Mitigation: separate names in admin (“Service Areas” vs fee zones); docs call out non-reuse.
- **[Risk] Google Maps key / cost on frontends** → Mitigation: client-side geocode only when needed; cache results; env-based keys never committed.
- **[Risk] Checkout rejects legacy addresses without lat/lng** → Mitigation: validation error prompting customer to re-pin; migrate/encourage coordinate backfill in frontend docs.
- **[Trade-off] Haversine vs GIS** → Slightly less precise than geodesic libraries / ellipsoidal models; acceptable for km-scale radii in Chattogram.

## Migration Plan

1. Add `service_area` app + migrations for `ServiceArea` and `ServiceAreaRequest`.
2. Mount URLs; ship admin CRUD + check/demand APIs; write docs.
3. Seed or admin-create initial hubs (e.g. Chawkbazar) before enabling frontend hard-gate UX.
4. Wire order-create gate behind clear errors; deploy backend before or with customer frontend that shows friendly copy.
5. Enable Admin Panel Service Areas section.
6. **Rollback:** feature-flag or short-circuit `assert_serviceable` to allow-all if emergency; hubs/requests tables can remain.

## Open Questions

- Exact default accuracy threshold (propose 500 m) — confirm with product.
- Whether demand CTA requires a separate endpoint vs `check` with `intent=demand`.
- Whether inactive hubs should still appear in admin map analytics as “nearest” for historical requests (historical rows keep FK even if hub later deactivated).
- Whether subscription activation paths beyond meal-package order create need the same gate in the same release (assume yes for any order create that schedules deliveries).
