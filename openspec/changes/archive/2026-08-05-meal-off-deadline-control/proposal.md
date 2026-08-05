## Why

Customers can already meal-off a scheduled lunch or dinner before the configured deadline, but they cannot turn that meal back on if they change their mind while the deadline has not yet passed. Kitchen prep and wallet charging need a clear lock: after the lunch/dinner meal-off deadline, Off and On must both be frozen so ops and billing stay consistent.

## What Changes

- Add **customer meal-on** (undo meal-off): restore a customer-skipped delivery to `scheduled` only while the same period deadline has not passed.
- Enforce the **same deadline gate** for both meal-off and meal-on: once business time is past the slot deadline, reject any Off/On change and leave existing status unchanged.
- Expose meal-on eligibility on customer delivery payloads (e.g. `can_meal_on`) alongside existing `can_meal_off` / `meal_off_deadline_at`.
- Reopen an order that was auto-completed solely because slots became terminal after meal-off, when meal-on restores a non-terminal slot (before deadline).
- Confirm and document default/on behavior: no meal-off → treat as meal on → normal delivery + wallet charge on `delivered`; meal-off (`skipped`) → no cook/delivery expectation and **no wallet debit** (already true for payment; keep aligned).
- Keep existing admin-configurable per-period deadlines (`lunch_off_time`, `dinner_off_time`, timezone) and existing calendar math (lunch on `D` → previous day + lunch time; dinner on `D` → same day + dinner time).
- Update customer/API docs and tests for Off/On + lock-after-deadline flows.

## Capabilities

### New Capabilities

- _(none)_ — meal-on extends the existing customer meal-off capability rather than introducing a separate domain.

### Modified Capabilities

- `customer-meal-off`: Add meal-on (undo) before deadline; lock both Off and On after deadline; eligibility fields; order reopen when undoing a completing skip.
- `meal-off-deadline-settings`: Clarify that configured lunch/dinner times gate **both** meal-off and meal-on eligibility (same deadline math).
- `meal-delivery-wallet-payment`: Reinforce that meal-on restores charge eligibility only via a later `delivered` mark (no charge on meal-on itself; still no charge while `skipped`).

## Impact

- **Orders services**: `orders/services/meal_off.py` (meal-on, shared deadline helpers, eligibility); possibly `order_status` / `order_delivery` for reopen-from-completed.
- **Orders API**: customer meal-on endpoint (or action) next to existing meal-off; serializer fields on delivery nested payloads.
- **Models**: no new settings fields expected; may clear `skip_source` / mark metadata on meal-on.
- **Tests / docs**: `orders/tests/test_customer_meal_off.py`, frontend/backend meal-off docs.
- **Wallet**: no new debit path; meal-on does not charge; delivery charge rules unchanged.
- **Admin meal-off settings**: behavior unchanged except docs that deadlines apply to Off and On.
