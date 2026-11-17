# Proposal

## Why

Guest Meal v1 is already shipped, but a re-audit against updated product rules shows material gaps: personal Meal-OFF does not block Guest Meal purchases (previously an explicit product decision), rider APIs expose `meal_quantity` and `guest_quantity` without a server-side total or summary box reconciliation, and paid Guest Meals can become operationally invisible when the linked `OrderDelivery` is skipped or missing. These gaps create kitchen/rider under-count risk and allow purchases that contradict the new “regular meal must be ON” rule.

## What Changes

- Enforce **personal Meal-OFF blocks Guest Meal** for the same `service_date` + `meal_period` on both preview and create (`PERSONAL_MEAL_OFF`, HTTP 422); revalidate at create time (do not trust preview).
- Distinguish **customer-requested Meal-OFF** (`OrderDelivery.status=skipped` + `skip_source=customer`) from admin/system skips; do not treat every `skipped` row as personal OFF.
- Prefer **blocking Meal-OFF** when a countable (scheduled) Guest Meal already exists for that slot (v1 has no cancel/refund), so paid guest boxes cannot disappear from rider/kitchen boards.
- Require a **resolvable subscription `OrderDelivery` stop** before create succeeds; reject (do not silently accept `delivery=null` after wallet debit).
- Add additive rider fields **`total_meal_quantity`** (and summary regular/guest/total/pending/delivered box metrics) without renaming existing keys; keep `meal_quantity` as regular-only and `guest_quantity` additive (no double-count).
- Harden eligibility/docs/tests around wallet floor, idempotency, quota locking, and delivery sync; supersede obsolete “Meal-OFF does not block Guest Meal” documentation and the prior OpenSpec decision in `guest-meal-order-system`.
- **Non-goals:** Guest Meal cancel/refund product, non-subscriber guest meals, renaming existing rider keys, rewriting wallet ledger strategy, or **BREAKING** removals of current API fields.

## Capabilities

### New Capabilities

- `guest-meal-order`: Corrected Guest Meal eligibility (incl. personal Meal-OFF), pricing snapshots, monthly quota, wallet debit + meal-stop floor, preview/create/usage APIs, idempotency, and domain errors.
- `guest-meal-delivery-integration`: Mandatory delivery linking, orphan prevention, parent deliver sync, kitchen demand guest units, and Meal-OFF ↔ existing Guest Meal interaction.
- `deliveryman-meal-box-totals`: Rider today-board and today-summary regular/guest/total box quantities with reconciliation and backward-compatible additive fields.

### Modified Capabilities

- `customer-meal-off`: Meal-OFF MUST be rejected when a countable Guest Meal exists for the same slot (until cancel/refund exists).
- `meal-demand-forecasting`: Demand MUST continue to include countable guest units and MUST stay consistent with the Meal-OFF / guest eligibility rules above.

## Impact

- **Orders:** `orders/services/guest_meal.py`, `orders/services/meal_off.py`, `orders/api/guest_meal_views.py` (+ serializers/OpenAPI), `orders/services/meal_demand.py`, tests under `orders/tests/`.
- **Delivery / rider:** `delivery_zones/services/board.py`, `delivery_zones/services/today_summary.py`, deliveryman views/serializers/docs/tests.
- **Docs:** `orders/docs/GUEST_MEAL_INTEGRATION_GUIDE.md`, backend/frontend guest-meal and meal-off docs, deliveryman today-ops docs; remove contradictory Meal-OFF allowance text.
- **OpenSpec:** New change `guest-meal-meal-off-rider-totals` (do **not** reopen completed `guest-meal-order-system`; supersede its Meal-OFF allowance decision). No DB migration expected unless orphan-hardening requires a non-null delivery constraint (assessed in design; prefer reject-at-create first).
- **Clients:** Mobile Express riders consume new total fields; customer app must handle `PERSONAL_MEAL_OFF` and Meal-OFF blocked-when-guest-exists errors.
