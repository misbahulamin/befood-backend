## Why

Bachelor customers on multi-day meal packages often skip a lunch or dinner when they will not eat at home. Today only admins can mark a delivery `skipped`, and there is no cutoff tied to cook prep (e.g. lunch for the 24th must be declined by 23rd 11:59pm; dinner for the 23rd by 23rd 2pm). Without customer meal-off before those deadlines, kitchen still plans food for people who will not take the meal.

## What Changes

- Let an authenticated customer **meal-off** an upcoming `OrderDelivery` slot (lunch or dinner) they own, which means that slot is no longer cooked/delivered for them.
- Enforce **configurable deadlines** (business timezone):
  - Default lunch off: previous calendar day at **23:59**
  - Default dinner off: same calendar day at **14:00** (2pm)
- Admin can change those deadline times (and timezone) via settings API (same singleton pattern as menu reveal settings).
- After a successful meal-off, the slot MUST appear as customer-skipped / no meal for kitchen and ops boards.
- Reject meal-off after the deadline, for other users’ slots, or for already terminal slots (`delivered` / `skipped` / `missed`).
- Optionally expose `can_meal_off` and deadline timestamp on delivery payloads so the app can show/hide the action.
- No refund/pricing change in this change (meal-off is operational skip only).

## Capabilities

### New Capabilities

- `customer-meal-off`: Customer-owned meal-off of a scheduled lunch/dinner delivery slot before the period deadline; ownership and state rules.
- `meal-off-deadline-settings`: Admin-configurable lunch/dinner meal-off cutoff times and timezone used to evaluate eligibility.

### Modified Capabilities

- (none in `openspec/specs/` — order delivery lives only in prior change artifacts; meal-off builds on existing `OrderDelivery` without amending archived main specs)

## Impact

- Orders: new customer meal-off endpoint/service; delivery serializer fields; possibly `skip_source` / note to distinguish customer vs admin skip.
- Settings: new singleton model or extension alongside `MenuRevealSettings` (prefer separate meal-off settings to avoid mixing reveal vs opt-out semantics).
- Admin: settings GET/PATCH; today-board / delivery lists already show `skipped`.
- Docs: `orders/docs/` backend + frontend; OpenAPI.
- Tests: deadline edge cases (lunch previous-day 23:59, dinner same-day 14:00), late reject, ownership, idempotency.
