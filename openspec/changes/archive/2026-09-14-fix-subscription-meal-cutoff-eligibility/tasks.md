## 1. Analysis lock-in (no code change)

- [x] 1.1 Confirm root cause in `ensure_subscription_deliveries` always sets `status=SCHEDULED` and that meal-off helpers are unused at create time
- [x] 1.2 Confirm auto-delivery only selects `status=scheduled` and will not be modified
- [x] 1.3 Confirm no DB migration is required (use `skipped` + `skip_source=system` + `note=cutoff_passed`)

## 2. Cutoff helper

- [x] 2.1 Add a small reusable predicate in `orders/services/meal_off.py` (e.g. `is_past_meal_cutoff`) that uses `meal_off_deadline` + settings timezone and treats `now > deadline` as past cutoff
- [x] 2.2 Unit-test the helper for lunch/dinner boundaries and Asia/Dhaka vs UTC wall-clock confusion

## 3. Slot generation fix

- [x] 3.1 In `ensure_subscription_deliveries`, when constructing each new `OrderDelivery`, if cutoff has passed set `status=skipped`, `skip_source=system`, `note` with stable token `cutoff_passed`, and set `marked_at`; otherwise keep `scheduled`
- [x] 3.2 Ensure existing `(service_date, meal_period)` rows remain untouched (idempotent create-only behavior)
- [x] 3.3 Do not change `auto_meal_delivery`, `auto_deliver_meals`, or wallet charge services

## 4. Tests

- [x] 4.1 Subscribe at 01:59 with lunch cutoff 02:00 → today's lunch `scheduled` (chargeable path)
- [x] 4.2 Subscribe at 02:01 with lunch cutoff 02:00 → today's lunch `skipped` / system / `cutoff_passed`; assert not selected by auto-delivery eligibility (no wallet debit)
- [x] 4.3 Subscribe at 15:59 with dinner cutoff 16:00 → dinner `scheduled`
- [x] 4.4 Subscribe at 16:01 with dinner cutoff 16:00 → dinner `skipped`
- [x] 4.5 Subscribe at 03:00 on a `both` plan → lunch skipped, dinner scheduled when dinner cutoff not passed
- [x] 4.6 Timezone test: settings `Asia/Dhaka`; assert cutoff uses Dhaka local time even when process time is UTC-aware
- [x] 4.7 Run focused subscription / meal-off related tests with `--keepdb`

## 5. Docs and QA notes

- [x] 5.1 Update `orders/docs/backend/` subscription (and meal-off cross-link if needed) to describe first-day cutoff-aware slot creation
- [x] 5.2 Document manual QA steps: configure cutoffs, subscribe before/after lunch and dinner, verify delivery statuses and that auto-delivery does not charge skipped cutoff meals
- [x] 5.3 Note forward-only safety: no backfill of pre-existing wrongly scheduled rows; no migration
