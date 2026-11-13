# Proposal

## Why

Admin stores Building / Floor / Flat on the customer delivery place (e.g. Abdul Baser: `Me likely hostel` / `5` / `619`), but the deliveryman today-board API only returns `full_address` (street line). The Delivery Man app already maps and can render those parts; riders still only see `Mcs tower,muradpur Chittagong` because the backend never puts building/floor/flat on the board payload.

## What Changes

- Extend each today-board **customer row** with additive fields `building_name`, `floor`, and `flat_number` (empty string when unknown)—same names as Admin / `CustomerDeliveryPlace`.
- Source those values from the delivery’s linked `CustomerDeliveryPlace` when present (and align snapshotting so future deliveries keep the parts even if the place FK is cleared later).
- Keep existing `full_address`, `area`, and `city` unchanged (additive only; not **BREAKING**).
- Update deliveryman board frontend docs (`zone-based-delivery.md` / today-ops docs) so clients know the three new keys.
- Add/adjust board tests proving a place with building/floor/flat appears on the rider board response.

## Capabilities

### New Capabilities

- `deliveryman-delivery-board`: Deliveryman today-board customer-row address contract, including structured building / floor / flat parts alongside street snapshots.
- `zone-delivery-frontend-docs`: Frontend documentation of the deliveryman board customer address fields so mobile/Admin clients stay aligned.

### Modified Capabilities

- (none — `deliveryman-delivery-board` / related board specs are not yet under `openspec/specs/`; prior work lived in change archives.)

## Impact

- **Backend**: `delivery_zones/services/board.py` (customer row dict + `select_related('delivery_place')`); `orders/services/delivery_address.py` (+ optionally `OrderDelivery` snapshot columns); board/unit tests under `delivery_zones/tests/`.
- **Docs**: `delivery_zones/docs/frontend/zone-based-delivery.md` (and deliveryman today-ops doc if it lists customer fields).
- **Clients**: `befood_deliveryman_mobile` already expects `building_name` / `floor` / `flat_number` after `delivery-contact-address-ui`; no mobile code required in this change once API ships.
- **Out of scope**: Admin Panel UI, changing how Admin formats the “·” joined display string, mobile UI work, renaming existing address snapshot fields.
