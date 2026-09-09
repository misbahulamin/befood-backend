## 1. Investigation close-out (no code changes)

- [ ] 1.1 Confirm design.md investigation report covers both kitchen endpoints (flow diagram, status inclusion table, cron/cache/timezone findings)
- [ ] 1.2 On one incident day, record Admin SPA request query params (`service_date`, `meal_period`) and which response fields were compared (`final_cooking_count` vs `total_customers` vs order-details `count`)
- [ ] 1.3 Read-only: load production `MealOffSettings` (`timezone`, `lunch_off_time`, `dinner_off_time`)
- [ ] 1.4 Read-only SQL: for incident `service_date` + `meal_period`, list `OrderDelivery` rows with `created_at` after the morning observation time (status, subscription/order id, note, skip_source)
- [ ] 1.5 Read-only SQL: check same-slot unique violations are absent; find customers whose `meal_service_blocked_low_balance` flipped during that day
- [ ] 1.6 Read-only: check meal-on transitions (`skipped`→`scheduled`, customer skip_source) and menu-publish timestamps overlapping the drift window
- [ ] 1.7 Append a short “incident confirmation” note under design.md Open Questions once production checks complete

## 2. Short-term ops / SPA hardening (optional; no billing changes)

- [ ] 2.1 Update Admin kitchen pages to always send explicit `service_date` + `meal_period` on requirement and order-details calls (including PDF print path)
- [ ] 2.2 Document in `orders/docs/frontend/meal-demand-kitchen-planning.md` that same-day count drift is live eligibility (subscribe/ensure/meal-on/unblock), not cache
- [ ] 2.3 Ensure UI hero uses `final_cooking_count` / order-details `count`, not `expected_meal_count` alone

## 3. Follow-up freeze implementation (deferred; separate apply after product answers)

- [ ] 3.1 Product decision: post-cutoff freeze exclude list (late create, low-balance resume, both) and whether auto-deliver must match kitchen freeze
- [ ] 3.2 Implement post-cutoff kitchen eligibility freeze for today-meal-requirement + today-order-details per `kitchen-demand-count-stability` without deleting deliveries
- [ ] 3.3 Add unit/API tests for pre-cutoff live growth, post-cutoff stable counts, and skipped cutoff_passed rows
- [ ] 3.4 Do not change wallet debit / `mark_delivery` charging unless product explicitly approved alignment in 3.1
- [ ] 3.5 Update backend + frontend kitchen docs and OpenAPI descriptions for freeze behavior
