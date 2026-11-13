# Design

## Context

See `proposal.md` for why. Observed gap:

- Admin / `CustomerDeliveryPlace` has `building_name`, `floor`, `flat_number`.
- `orders.services.delivery_address.snapshot_fields_from_place` copies only label, full_address, area, city, lat/lng onto `OrderDelivery`—not building/floor/flat. `OrderDelivery` has no snapshot columns for those three.
- `delivery_zones.services.board.build_deliveryman_board` customer rows set `'full_address': delivery.delivery_full_address_snapshot` (plus area/city) and never emit building/floor/flat.
- Board queryset `select_related` does not include `delivery_place`, so even a live FK read would need that join.
- Mobile (`delivery-contact-address-ui`) already maps `building_name` / `floor` / `flat_number` and renders them when present.

## Goals / Non-Goals

**Goals:**

- Additive board JSON keys matching Admin place field names.
- Correct values for today’s rider board without inventing data.
- Durable enough that place edits and null FKs do not silently drop door-level detail for in-flight deliveries.
- Docs + tests so mobile can rely on the contract.

**Non-Goals:**

- Changing Admin UI formatting (`·` joined lines).
- Mobile app code in this change.
- Backfilling every historical delivered row unless cheap via place FK live-read.
- Exposing landmark or other unused place fields unless already on the board.

## Decisions

### 1. Emit live place fields on the board + extend snapshots for future writes

- **Choice:**
  1. `select_related('delivery_place')` on the board delivery queryset.
  2. When building each customer row, set `building_name` / `floor` / `flat_number` from `delivery.delivery_place` when the FK is set; otherwise empty strings.
  3. Extend `snapshot_fields_from_place` (and `OrderDelivery` with three blank `CharField`s + migration) so new/resync snapshots store the parts; prefer **snapshot columns when non-empty**, else fall back to live place (so today’s already-snapshotted rows with a live FK still work immediately).
- **Why:** Live place fixes Abdul Baser-style rows today without waiting for resync; snapshots match existing address architecture and survive `SET_NULL` on place delete.
- **Alternatives considered:**
  - Live-only (no migration) — faster, but loses parts if FK cleared; rejected as sole long-term approach.
  - Snapshot-only without live read — needs backfill before production riders see data; worse UX for this bugfix.

### 2. Field names and empty semantics

- **Choice:** JSON keys `building_name`, `floor`, `flat_number` as strings; always present; `""` when unknown.
- **Why:** Matches Admin serializers / mobile DTO keys already landed.
- **Alternatives:** Nested `address: {…}` object — **BREAKING** for clients; rejected.

### 3. Docs

- **Choice:** Update the customer example in `delivery_zones/docs/frontend/zone-based-delivery.md` and the field list in `deliveryman-today-ops.md` if it enumerates customer keys.
- **Why:** Spec `zone-delivery-frontend-docs` requires discoverability.

### 4. Tests

- **Choice:** Board/API test: place with building/floor/flat → customer row contains those values; place without → empty strings; `full_address` still present.
- **Why:** Locks the contract for mobile.

## Risks / Trade-offs

- **[Risk] `delivery_place` FK null on some live rows** → Mitigation: snapshot columns + optional one-time resync of future scheduled deliveries after deploy; empty strings rather than guessing.
- **[Risk] N+1 if select_related omitted** → Mitigation: require `delivery_place` on the existing board queryset select_related list.
- **[Risk] Place edited after snapshot** → Mitigation: live fallback prefers current place when snapshot parts empty; documented that board may reflect live place for parts until snapshots are populated. Acceptable for rider “find the door” accuracy.

## Migration Plan

1. Add nullable/blank snapshot columns on `OrderDelivery`; update `snapshot_fields_from_place` + save `update_fields` lists.
2. Update board row builder + select_related; ship docs.
3. Deploy; optionally run existing `resync_future_scheduled_deliveries` / backfill helpers so snapshots fill for upcoming days.
4. Rollback: revert board keys (mobile tolerates missing/empty); snapshot columns can remain unused.

## Open Questions

- None blocking: mobile keys already fixed; empty-string vs null — choose always-present empty strings as above.
