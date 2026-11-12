# Design

## Context

See proposal.md — Why. Production already runs Zone → Location → Customer on AWS via `delivery_zones` + `CustomerProfile.delivery_location`. Board/ops join `OrderDelivery` → customer → `delivery_location` → zone. Admin Panel uses `/api/v1/web/delivery-zones/`, `/api/v1/web/delivery-locations/`, and `PATCH …/customers/{id}/delivery-location/`. Street addresses (`CustomerDeliveryPlace`) and `ServiceArea` stay out of scope.

Constraints: thin views + services; `PublicIdMixin`; no downtime-friendly hard cuts during lunch/dinner windows; frontend lives outside this repo (contract via docs).

## Goals / Non-Goals

**Goals:**

- Persist Zone → Location → **SubLocation** → Customer with derived location/zone.
- Expand–contract schema and API so AWS deploy does not blank routing mid-meal.
- Keep board/ops correct when customers are only on sub-locations.
- Ship frontend docs + a clear Admin Panel implementation plan for `/admin/delivery-zones`.

**Non-Goals:**

- Building the React Admin Panel inside this backend repo.
- GPS / map auto-assignment for sub-locations.
- Rewriting historical `OrderDelivery.logistics_location` rows (optional additive `logistics_sub_location` only).
- Removing `DeliveryLocation` as a hierarchy node.

## Decisions

### 1. New model `DeliverySubLocation` under `DeliveryLocation`

- **Choice:** Add `DeliverySubLocation` in `delivery_zones` with FK `location` → `DeliveryLocation` (`PROTECT`), `name`, `priority`, `status`, `public_id`, optional unused geo hooks mirroring location/zone.
- **Why:** Matches product hierarchy; keeps Location as the neighborhood bucket riders already know.
- **Alternatives:** Flatten “fake locations” per stop — loses shared location identity. Nested JSON on location — not queryable for boards/filters.

### 2. Customer truth moves to `delivery_sub_location` FK

- **Choice:** Add nullable `CustomerProfile.delivery_sub_location` → `DeliverySubLocation`. Derived location = `sub.location`; derived zone = `sub.location.zone`. During expand phase, keep `delivery_location` populated in sync (mirror of parent location) so old readers keep working; contract phase stops writing/reading it as source of truth and later drops or freezes it.
- **Why:** Single assignment row; cascade on location/sub-location moves without bulk customer updates.
- **Alternatives:** Keep only `delivery_location` and encode sub-stop in free text — not filterable. Dual independent FKs without sync — drift risk.

### 3. Expand–contract migration (AWS-safe)

Phases (deployable separately):

| Phase | Backend | Data | Clients |
|-------|---------|------|---------|
| **Expand** | Add `DeliverySubLocation` table; add nullable `delivery_sub_location_id`; add APIs; board/ops prefer sub-location when set else fall back to location | Data migration: for each existing `DeliveryLocation`, create one **default** sub-location (`name` = location name or `"Default"`, `priority=1`, `is_default=True` or naming convention); backfill every customer with `delivery_location_id` → that location’s default sub-location; set both FKs | Old Admin Panel still works |
| **Bridge** | Assign API accepts `delivery_sub_location_public_id` (preferred) and legacy `delivery_location_public_id` (maps to default sub-location); serializers expose sub-location + derived location/zone; filters add `sub_location_public_id` / `has_delivery_sub_location` while keeping location/zone filters via join | Integrity check: customers with location must have matching sub-location parent | New Admin Panel ships dual-aware |
| **Contract** | Board/ops require active sub-location (no location-only fallback); reject location-only assign; stop mirroring writes if desired | Optional later migration: null `delivery_location` or remove column in a follow-up change after all clients upgraded | Old location-only assign removed |

- **Why:** Avoids one-shot breaking deploy during meal windows; rollback of Expand is additive-only (safe).
- **Alternatives:** Big-bang cutover — high risk on AWS if frontend lags. Soft “sub-location optional forever” — leaves dual truth forever.

### 4. Default sub-location backfill rule

- **Choice:** Every existing location gets exactly one default sub-location at migration time; all current customers on that location move to it. Admins later create Gate A/B and reassign customers.
- **Why:** Zero customer loses zone membership after migrate; boards keep working with identical grouping until ops splits stops.
- **Alternatives:** Backfill only locations that have customers — empty locations without a default break legacy location-assign mapping; prefer creating defaults for all locations.

### 5. API surface

- **Choice:** Flat collection `/api/v1/web/delivery-sub-locations/` (list/create + detail) filtered by `location_public_id` / `zone_public_id`, plus optional `POST …/delivery-locations/{id}/sub-locations/reorder/` mirroring location reorder. Customer assign: extend existing nested action to accept `delivery_sub_location_public_id` (new primary) and keep temporary location field for Bridge.
- **Why:** Matches existing flat zone/location URL style; Admin Panel can cascade selects Zone → Location → Sub-location.
- **Alternatives:** Deep nesting only under locations — harder for global search/filter.

### 6. Board and ops query path

- **Choice:** After Bridge, resolve operational stop via `customer.delivery_sub_location` (select_related location/zone). Group board: zone → locations (by location.priority) → sub-locations (by sub.priority) → customers. Ops counts add `sub_locations[]` under each location. Unassigned = no sub-location (Bridge may treat “location set but sub null” as transitional and backfill-fixable).
- **Why:** Same neighborhood, multiple stops is the product reason for this change.
- **Alternatives:** Flat list of sub-locations without location headers — worse UX for riders who still think in neighborhoods.

### 7. Location empty/delete rules

- **Choice:** `delete_location_if_empty` / deactivate guards check customers via `location.sub_locations__customers` (and block if any sub-location has customers). Deleting a location that still has sub-locations may require sub-locations empty first or cascade-block.
- **Why:** Prevents orphaning after FK moves to sub-location.

### 8. Attribution on `OrderDelivery`

- **Choice:** Add nullable `logistics_sub_location` FK for future rider completion snapshots; do not rewrite historical rows in this change. Live board continues to use customer current assignment.
- **Why:** Additive, low risk; full historical backfill is optional later.

### 9. Feature flag / settings for compatibility

- **Choice:** Settings flag e.g. `DELIVERY_SUB_LOCATION_LEGACY_LOCATION_ASSIGN=True` during Bridge; set False in Contract after Admin Panel ships.
- **Why:** Instant rollback of API behavior without redeploying schema.

### 10. Frontend (Admin Panel) implementation plan (out-of-repo code)

Target page: `http://127.0.0.1:5173/admin/delivery-zones`.

Recommended UI shape (contract for FE team; details in frontend doc task):

1. Keep existing Zone list/create/edit/deactivate and Location under zone.
2. Add Sub-location panel/drawer under selected Location (name, priority, status, reorder).
3. Customer assign flows (delivery-zones page and/or customer detail): cascade Zone → Location → Sub-location; submit `delivery_sub_location_public_id`.
4. During Bridge: if API still returns only location for old clients, FE still reads new fields when present; never clear sub-location accidentally.
5. Deploy order: backend Expand+Bridge → FE release → flip Contract flag → later cleanup.

## Risks / Trade-offs

- **[Risk] Dual FK drift (`delivery_location` vs sub-location parent)** → Mitigation: single service `assign_customer_sub_location` always sets both during Bridge; integrity management command / test asserts parent match.
- **[Risk] Board empty if Expand deploys without backfill** → Mitigation: backfill in same release migration; deploy only after `migrate` succeeds; smoke-check ops unassigned count ≈ 0 (except truly unassigned).
- **[Risk] Frontend lags behind Contract flag** → Mitigation: keep Bridge flag true until FE confirms; staged AWS env first.
- **[Risk] Priority uniqueness conflicts when creating default + new sub-locations** → Mitigation: default uses priority 1; new creates use next free priority in service layer (same pattern as locations).
- **[Risk] N+1 on nested board** → Mitigation: `select_related` sub-location/location/zone; reuse existing board prefetch patterns.
- **[Trade-off] Temporary dual fields increase serializer noise** → Accepted for safe cutover; Contract removes legacy assign.

## Migration Plan

1. **Precheck (staging):** Snapshot counts: customers with `delivery_location_id`, board totals per zone for a sample date.
2. **Expand deploy:** Ship models + nullable FK + CRUD APIs + dual-read board/ops; run migrations + backfill; verify every formerly assigned customer has `delivery_sub_location_id`; boards non-empty.
3. **Bridge:** Enable legacy location assign mapping; publish updated frontend docs; FE ships dual-aware Admin Panel.
4. **Contract:** Disable legacy assign; board requires sub-location; monitor 4xx on old payloads.
5. **Cleanup (optional follow-up change):** Remove `delivery_location` FK / stop mirroring; drop flag.
6. **Rollback:** Expand/Bridge — revert app code; leave additive columns (safe). Do not reverse backfill casually; if needed, re-point reads to `delivery_location` while column still populated.

## Open Questions

- Exact default sub-location display name (`"Default"` vs copy location name) — product copy preference; does not change schema. Default assumption: **copy location name** so existing board labels stay familiar until ops renames/splits.
- Whether Admin Panel customer assign lives only on customer detail or also bulk on delivery-zones page — FE can do either; API supports per-customer assign either way.
