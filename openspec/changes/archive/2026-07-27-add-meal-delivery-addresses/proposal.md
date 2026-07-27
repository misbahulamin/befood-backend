## Why

Customers currently store only `present` and `permanent` addresses, and delivery is assumed to be the default present address. Real meal delivery needs are richer: lunch at the office, dinner at home, weekend meals at the present address, and occasional one-off destinations. Without meal-period and day-of-week aware delivery preferences, riders and ops cannot reliably know where to deliver each lunch/dinner slot, and customers cannot manage this without confusion.

## What Changes

- Introduce a dedicated **delivery address book** for customers (many saved destinations such as Home, Office, Hostel), separate from identity addresses (`present` / `permanent`).
- Allow customers to keep many delivery addresses, but expose a simple preference model: **at most one active lunch destination and one active dinner destination** (or one shared address for both).
- Support **weekday override rules** so weekday lunch can go to Office while weekend (or specific days) lunch goes to Home/present—without forcing customers to change the default every day.
- Resolve and **persist the effective delivery address on each `OrderDelivery` slot** (snapshot) so historical deliveries remain correct even if preferences change later.
- Keep the customer UX deliberately simple: save places once, pick “Lunch goes here / Dinner goes here”, optionally set “On these days, use another place”.
- Extend customer APIs and docs for address book + preference management; extend order/delivery APIs so ops and riders see the resolved address per slot.
- **Out of scope for this change:** live map/geofencing enforcement, rider routing optimization, multi-recipient household sharing, per-single-order ad-hoc address override UI beyond preference rules (may be a later seam), changing permanent/present identity semantics.

## Capabilities

### New Capabilities
- `delivery-address-book`: Customer can CRUD labeled delivery destinations (independent of present/permanent), with ownership and soft limits for UX clarity.
- `meal-delivery-preferences`: Customer sets active lunch/dinner delivery destinations and optional day-of-week overrides; system resolves one address per meal period for a given service date.
- `delivery-address-resolution`: When generating or updating `OrderDelivery` rows, resolve and snapshot the effective delivery address (and display fields) for that `service_date` + `meal_period`.

### Modified Capabilities
- (none — no existing main specs for customer addresses / order delivery location)

## Impact

- **Apps:** `user_management/` (address model extension or sibling delivery-address model, services, serializers, views, admin, profile-completion hooks), `orders/` (OrderDelivery address snapshot fields, generation/resolution service hooks).
- **APIs:** Customer address book + preference endpoints under `user_management/`; delivery list/detail responses under `orders/` include resolved address for ops/customer.
- **Auth:** Token auth + `HasCustomerProfile`; object ownership on all customer address/preference mutations; no cross-customer access.
- **Clients:** Mobile/web need a simple “My places” + “Where should lunch/dinner go?” flow; ops screens show per-slot destination.
- **Docs/tests:** New/updated backend & frontend docs; tests for ownership, validation, weekday overrides, resolution precedence, and delivery snapshot integrity.
- **Migration:** Existing `is_default_delivery` present address becomes the initial lunch+dinner preference (and first delivery-book entry or linked default) so current customers keep working without re-setup.
