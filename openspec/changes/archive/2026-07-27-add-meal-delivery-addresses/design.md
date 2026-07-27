## Context

Today `CustomerAddress` stores `present` and `permanent` identity addresses. Only a `present` row may be `is_default_delivery=True`, and profile completion treats that flag as “has a delivery address.” Orders expand into `OrderDelivery` rows keyed by `service_date` + `meal_period` (`lunch` | `dinner`), but **no address is stored on the delivery slot**. Ops therefore cannot see where each lunch/dinner should go, and customers cannot express “weekdays lunch at office, weekends at home” without constantly flipping a single default.

Stakeholders: customers (mobile/web) who need an obvious “where does my food go?” flow; kitchen/ops/riders who need a stable destination per slot; product, which wants a simple UI even if resolution rules are rich on the backend.

Constraints:
- Keep `present` / `permanent` identity semantics; do not overload them as the only delivery destinations.
- Follow project patterns: services in `user_management/services/` and `orders/services/`, thin DRF views, Token auth, customer ownership, `PublicIdMixin` on public resources.
- Frontend must stay simple: save places once, set lunch/dinner defaults, optionally override by weekday.
- Snapshot resolved address onto `OrderDelivery` so preference changes do not rewrite history.

## Goals / Non-Goals

**Goals:**
- Customer **delivery place book**: many labeled destinations (Home, Office, Hostel, …).
- **Active preferences**: at most one default place for lunch and one for dinner (same place allowed for both).
- **Weekday overrides**: for a given meal period + weekday, optionally use a different place.
- **Resolution service**: given customer + service date + meal period → one effective place.
- **Persist snapshot** on each `OrderDelivery` at generation/update time.
- Migrate existing default present address into a usable first place + lunch/dinner defaults so current customers keep working.
- Customer APIs + docs; expose resolved destination on delivery reads for customer/ops.

**Non-Goals:**
- Replacing or removing present/permanent addresses.
- Live map routing, zone pricing, or geofence hard-blocks (coords remain optional fields).
- One-off “change only tomorrow’s lunch” calendar UI as a first-class product (leave a future seam; weekday rules cover the stated weekly pattern).
- Multi-person / shared household address books.
- Changing meal-off cutoffs or skip logic.

## Decisions

### 1. Separate delivery places from identity addresses
- **Choice:** Add `CustomerDeliveryPlace` (name TBD in impl: keep under `user_management`) as the delivery address book. Keep `CustomerAddress` for `present` / `permanent` only. Soft-deprecate “present = delivery” as the sole mechanism: `is_default_delivery` remains for backward compatibility / profile completion until clients migrate, then can mirror the lunch+dinner default place.
- **Rationale:** Present/permanent are KYC/profile concepts; office vs home delivery is operational. Mixing types in one enum forces awkward rules (“only present can be default”).
- **Alternatives considered:**
  - Add `address_type=delivery` on `CustomerAddress` — simpler table, but identity and delivery share validation/admin UX poorly.
  - Force customers to mark present as office — fails the product story.

### 2. Delivery place shape
- **Choice:** `CustomerDeliveryPlace`: `PublicIdMixin`, FK `customer_profile`, `label` (e.g. Home/Office), address fields mirroring current address usefulness (`full_address`, `city`, `area`, `building_name`, `floor`, `flat_number`, `landmark`, optional `latitude`/`longitude`), `is_active` (soft disable), timestamps. Soft max places per customer (e.g. 10) enforced in service for UX, not a hard product limit forever.
- **Rationale:** Labels make the frontend dropdown human; reuse familiar address fields.
- **Alternatives considered:** Free-form single text blob only — worse for ops sorting by area.

### 3. Preference model: defaults + weekday overrides
- **Choice:**
  - `MealDeliveryPreference` (1:1 with `CustomerProfile`): `lunch_place` FK nullable, `dinner_place` FK nullable (both must belong to the same customer when set).
  - `MealDeliveryDayOverride`: unique `(customer_profile, meal_period, weekday)` → `place` FK. Weekday as `0–6` (Monday=0, ISO-style) documented in API.
- **Rationale:** Matches product: many saved places, only 1–2 “active” defaults; weekday exceptions without a calendar grid of every date.
- **Alternatives considered:**
  - Only one global default + per-slot edits — too weak for office/weekend pattern.
  - Full date-range schedule table — powerful but heavy for frontend v1.
  - Separate “active” flags on places (max 2) without meal-period binding — ambiguous which is lunch vs dinner.

### 4. Resolution precedence
- **Choice:** For `(customer, service_date, meal_period)`:
  1. Day override for `weekday(service_date)` + `meal_period`, if present and place active.
  2. Else preference default for that `meal_period`, if set and place active.
  3. Else fallback: active delivery place linked from migration / or present `is_default_delivery` address mapped to a place / or first active place by `created_at`.
  4. If nothing resolves → treat as configuration error for new delivery generation (fail loudly in service / leave snapshot null only for legacy rows during migration window — document).
- **Rationale:** Predictable; customers only manage exceptions when needed.
- **Alternatives considered:** Date-specific overrides first — deferred to a future change.

### 5. Snapshot on `OrderDelivery`
- **Choice:** Add to `OrderDelivery`:
  - optional FK `delivery_place` (`SET_NULL` on place delete)
  - snapshot columns: `delivery_label_snapshot`, `delivery_full_address_snapshot`, `delivery_area_snapshot`, `delivery_city_snapshot`, optional lat/lng snapshots
  - Resolve and write snapshots when delivery rows are **created**; re-resolve only for **future `scheduled`** slots when preferences change (optional service `resync_future_delivery_addresses(customer)`), never rewrite `delivered` / `skipped` / `missed` history.
- **Rationale:** Ops and disputes need the address that applied that day; deleting a place must not erase history.
- **Alternatives considered:**
  - Live join only to place — breaks when place edits/deletes.
  - Snapshot only on order header — wrong when lunch/dinner/days differ.

### 6. Frontend-simple API surface
- **Choice:** Expose three customer-facing resources (names illustrative):
  - `GET/POST /user_management/customer/delivery-places/` + detail PATCH/DELETE
  - `GET/PUT /user_management/customer/delivery-preferences/` — body: `{ lunch_place_id, dinner_place_id }` (public UUIDs)
  - `GET/PUT /user_management/customer/delivery-preferences/day-overrides/` — replace-set or upsert list of `{ meal_period, weekday, place_id }`
  - Convenience read: `GET .../delivery-preferences/preview/?from=&to=` returning resolved place per date+period for calendar UI (optional but recommended for trust).
- **Rationale:** Backend complexity stays in services; clients only manage places + two dropdowns + optional weekday chips.
- **Alternatives considered:** Single mega PATCH on profile — harder to validate and document.

### 7. UX contract (for frontend docs)
- **Choice:** Document a three-step mental model:
  1. **My places** — add Home / Office / …
  2. **Usual delivery** — “Lunch → …”, “Dinner → …” (same place OK)
  3. **Exceptions** — “On weekdays, lunch → Office” via weekday toggles
- Do **not** ask customers to understand resolution precedence; preview endpoint/UI shows “This week your lunch goes to …”.
- **Rationale:** User asked for simple frontend even if backend is hard.

### 8. Auth and ownership
- **Choice:** Same customer guards as address APIs (`HasCustomerProfile` / verified-customer consistency with sibling endpoints). All place/preference mutations scoped to `request.user.customer_profile`. Foreign `public_id` → `404`.
- **Rationale:** BOLA prevention; matches existing address viewsets.

### 9. Profile completion & legacy `is_default_delivery`
- **Choice:** Profile completion “delivery_address” becomes true when lunch and dinner preferences required for the customer’s active meal periods are set **or** (transition) a present default still exists. Data migration: for each customer with present `is_default_delivery`, create a `CustomerDeliveryPlace` (label `Home` or from area), set both lunch and dinner preferences to it.
- **Rationale:** Zero-config continuity for existing users.
- **Alternatives considered:** Force re-onboarding — bad churn.

### 10. Hook into order delivery generation
- **Choice:** Wherever `OrderDelivery` rows are bulk-created (order purchase / schedule expansion service), call `resolve_delivery_address(...)` and write snapshots in the same transaction.
- **Rationale:** Single write path; avoids null destinations on new orders.
- **Alternatives considered:** Nightly backfill job only — leaves a window of missing addresses.

### 11. Admin
- **Choice:** Admin for delivery places, preferences, day overrides; show snapshot fields on `OrderDelivery` admin readonly.
- **Rationale:** Ops support without DB diving.

## Risks / Trade-offs

- **[Risk] Preference change mid-cycle confuses customers if past slots rewrite** → Mitigation: only resync future `scheduled` rows; snapshots immutable after non-scheduled status.
- **[Risk] Place deleted while referenced by preferences** → Mitigation: block delete if used as lunch/dinner/override, or require reassign; soft-deactivate preferred over hard delete when referenced by historical snapshots (FK SET_NULL on snapshot FK is fine).
- **[Risk] Frontend still feels complex with weekday matrix** → Mitigation: hide overrides behind “Different on some days?”; defaults alone satisfy many users; preview week strip builds trust.
- **[Risk] Dual system during migration (`is_default_delivery` + preferences)** → Mitigation: migration backfill + resolution fallback chain; document deprecation of present-as-only-delivery in frontend docs.
- **[Risk] Timezone weekday mismatch** → Mitigation: compute weekday in `Asia/Dhaka` (project meal timezone), document in API.

## Migration Plan

1. Ship models + migrations (places, preferences, overrides, OrderDelivery snapshot fields).
2. Data migration: present default → delivery place + lunch/dinner prefs.
3. Deploy APIs; keep old address endpoints working.
4. Wire resolution into delivery creation; optional management command to backfill snapshots for future scheduled deliveries.
5. Update frontend to places + preferences UX; show preview.
6. Later (separate change): stop treating present `is_default_delivery` as primary; keep present for profile only.

Rollback: new tables/columns are additive; disable new endpoints and fall back to present default if needed. Do not drop snapshot columns once written in production without a follow-up plan.

## Open Questions

- Exact soft cap on number of delivery places (propose 10).
- Whether dinner-only or lunch-only package customers must set only the relevant preference (recommend: only require periods present on active orders / meal selection).
- Whether customer-initiated “resync future deliveries” is automatic on preference save (recommend: yes, automatic for `scheduled` future slots).
- Ops-facing list filters by delivery area — nice-to-have, not blocking v1.
