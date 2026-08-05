## 1. Analysis and regression baseline

- [x] 1.1 Confirm current charge path uses `Order.per_meal_price_snapshot` in `orders/services/meal_payment.py` and document all average-rate call sites (order create, eligibility, public offering, wallet docs)
- [x] 1.2 Trace multi-package July publish/sync/delete/reopen paths and note any code that can mutate a non-target schedule
- [x] 1.3 Add failing regression tests: lunch vs dinner different charges; publish package A does not change package B; ingredient price change leaves published slot price unchanged

## 2. Slot final price model and calculation

- [x] 2.1 Add snapshot fields on `MonthlyMenuSlot` (`final_meal_price_snapshot`, ingredient/operational/profit snapshots; optional line JSON) plus migration
- [x] 2.2 Extract or reuse `build_one_meal_price_preview` into a shared service that prices a slot’s ingredients + month op cost + plan profit
- [x] 2.3 On `publish_schedule`, compute and persist snapshots for every assigned slot; reject publish if costing cannot resolve
- [x] 2.4 On unpublish, define and implement snapshot clear-or-retain behavior per design decision (document in code comments + docs)
- [x] 2.5 Data migration: backfill snapshots for already-published schedules from current catalog + plan/month costs

## 3. Delivery wallet charge uses slot price

- [x] 3.1 Update `charge_delivered_meal` to resolve published slot by order meal + `service_date` + `meal_period` and debit `final_meal_price_snapshot`
- [x] 3.2 Reject mark-delivered when published slot or snapshot is missing (no silent average fallback)
- [x] 3.3 Persist charged amount on `OrderDelivery` (e.g. `charged_amount`) and enrich wallet metadata with slot final price context
- [x] 3.4 Keep idempotency (`meal-delivery:{delivery.public_id}`), insufficient/frozen wallet rejection, and no charge for skip/missed
- [x] 3.5 Optional feature flag to revert to average snapshot only for emergency rollback; default to slot pricing

## 4. Package × month menu isolation

- [x] 4.1 Verify and harden schedule create/assign/publish/unpublish/delete to operate only on the target schedule public_id / plan
- [x] 4.2 Verify `apply_sync` mutates only the explicit target; add/adjust tests for source + sibling packages unchanged
- [x] 4.3 Verify reopen/delete of one plan’s schedule never touches sibling packages’ schedules
- [x] 4.4 Audit list/filter serializers so APIs never collapse to “one menu per month”; fix any buggy filter
- [x] 4.5 Confirm ingredient delete remains PROTECT for slot items and does not hide other packages’ menus

## 5. API serializers and OpenAPI

- [x] 5.1 Expose admin schedule slot `final_meal_price` (null in draft, set when published) in serializers + OpenAPI
- [x] 5.2 Expose delivery `charged_amount` / payment fields on mark-delivery responses + OpenAPI
- [x] 5.3 Optionally expose customer package-menu slot `final_meal_price` (per open question; default admin-first if undecided)
- [x] 5.4 Ensure public offering still labels/uses `per_meal_rate` as estimate only (no contract break beyond additive fields)

## 6. Tests

- [x] 6.1 Unit/service tests for slot final price formula (lunch 62 / dinner 38 style cases)
- [x] 6.2 Publish immutability: change ingredient price after publish → snapshots unchanged
- [x] 6.3 Delivery charge tests updated: amount = slot snapshot; lunch ≠ dinner; missing snapshot → 422; no double charge
- [x] 6.4 Multi-package isolation tests for publish, assign replace, delete, sync apply, customer package-menu both packages present
- [x] 6.5 Run related suites: meal schedule, cycle calculations, meal delivery wallet payment, full order process, customer package menu

## 7. Documentation and frontend instructions

- [x] 7.1 Update `orders/docs/backend|frontend/meal-delivery-wallet-payment.md` for slot-based charge amount
- [x] 7.2 Update `meals/docs` (monthly menu schedule + cycle costing) for slot snapshots, immutability, average vs final price
- [x] 7.3 Write frontend instruction notes: do not assume constant debit = `per_meal_price_snapshot`; show per-slot final price after publish; cache keys must include `meal_public_id` + year + month so one package publish cannot clear another package’s UI state
- [x] 7.4 Document wallet history: amounts may differ per lunch/dinner; use `meal_period` + `service_date` for display
