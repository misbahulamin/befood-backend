## 1. Board status modes & additive package fields

- [x] 1.1 Extend `build_deliveryman_board` (and query serializer) to support exclusive status modes: default/`scheduled` pending, `delivered` only, while keeping `include_delivered` backward-compatible
- [x] 1.2 Add additive customer-row fields: `package_name`, `package_public_id` (nullable); keep `meal_name`, `menu_items_label`, `status` unchanged
- [x] 1.3 For delivered rows, add `delivered_at` (prefer logistics `delivered_at` else `marked_at`) and rider attribution fields when `delivered_by_rider` is set
- [x] 1.4 Ensure `select_related` covers meal public ids / rider display name without N+1

## 2. Today summary metrics & package breakdown

- [x] 2.1 Implement `build_deliveryman_today_summary` using the same zone + `get_current_delivery_period` + low-balance exclusion scope as the board
- [x] 2.2 Return stop-based `total`, `delivered`, `pending` plus dynamic `packages[{package_public_id, package_name, count}]` via aggregation (no hardcoded names)
- [x] 2.3 Add `GET .../deliveryman/deliveries/today-summary/` view, serializer/OpenAPI, and URL mount under existing deliveryman routes

## 3. Mark delivered & customer activity

- [x] 3.1 Verify deliveryman mark path already persists status, `marked_by`/`marked_at`, `delivered_by_rider`, `delivered_at`, zone checks, and idempotency; fix only documented gaps
- [x] 3.2 Enrich `build_activity_events` `meal_delivered` summary + refs with Delivery Man identity when `delivered_by_rider` is present
- [x] 3.3 Confirm mark + logistics attribution remain inside existing `transaction.atomic` boundaries (no partial delivered-without-attribution regressions)

## 4. Tests

- [x] 4.1 Tests: pending vs delivered board filters; mark moves stop pending→delivered; other zone excluded
- [x] 4.2 Tests: today-summary totals match fixture math; package breakdown counts; unauthorized / other-rider scope denied
- [x] 4.3 Tests: additive package fields present; existing keys unchanged; delivered attribution fields after mark
- [x] 4.4 Tests: customer activity `meal_delivered` includes rider when attributed; still works when rider missing
- [x] 4.5 Tests: duplicate mark safe; Asia/Dhaka / meal-off period resolution (client date ignored)

## 5. Documentation

- [x] 5.1 Update backend docs for deliveryman board + new today-summary (request/response, auth, errors)
- [x] 5.2 Add/update frontend doc for BeFood Express tabs, summary KPIs, package fields, and backward-compat notes (mobile implementation out of scope)
- [x] 5.3 Refresh OpenAPI/`extend_schema` for changed/new endpoints
