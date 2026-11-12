# Tasks

## 1. Models and migrations

- [x] 1.1 Add `SubscriptionCancellation` model (subscription FK, customer FK, reason_code choices incl. migration-only `unknown`, optional reason_text, cancelled_by customer|admin|system, created_at) with indexes and verify `makemigrations` output is clean
- [x] 1.2 Add `ChurnFollowUp` model (customer FK, status choices, note, admin FK, timestamps) with indexes and verify migration applies on a fresh/test DB
- [x] 1.3 Add/confirm indexes on `CustomerSubscription` cancel date/status fields and verify migration includes them
- [x] 1.4 Data migration backfilling `SubscriptionCancellation(reason_code=unknown)` for existing cancelled subscriptions; verify count matches cancelled rows without reasons

## 2. Shared lifecycle service

- [x] 2.1 Implement `orders/services/customer_lifecycle.py` with Asia/Dhaka churn_date, mutually exclusive lifecycle classification helpers, and queryset annotation builders; verify unit tests for never_subscribed, unsubscribed, at_risk, won_back, active precedence
- [x] 2.2 Implement at_risk predicates (blocked days v1, meal-off days ≥5/7, wallet < one-day cost) and verify edge-case unit tests including currently-blocked silent churn
- [x] 2.3 Document lifecycle rules in `orders/docs/backend/customer-lifecycle-churn.md` and verify examples match the service behavior

## 3. Cancellation reason wiring

- [ ] 3.1 Require `reason_code` (+ optional `reason_text`) on customer `current/cancel` and admin cancel serializers/views; verify 422 when missing/invalid and no status change
- [ ] 3.2 Persist `SubscriptionCancellation` inside the cancel transaction; map cancelled_by from cancel_source; verify customer/admin/system paths in tests
- [ ] 3.3 Reject client-supplied `unknown` reason_code; verify OpenAPI/docs for cancel request body updated

## 4. Customer list enrichment and filters

- [ ] 4.1 Extend `LIST_QUERY_ALLOWLIST` / sort allowlist with lifecycle, churned_from/to, cancel_reason, package, churn/tenure sorts; verify unknown keys still 400
- [ ] 4.2 Annotate customer list queryset with lifecycle fields (no Python full-table loop) and serialize new row fields; verify list response shape and filter tests
- [ ] 4.3 Keep `inactive_subscription` working; verify overlap documented and both filters still pass existing tests

## 5. Churn APIs

- [ ] 5.1 Add `GET /api/v1/web/churn/customers/` paginated list using shared filters; verify authz and default unsubscribed scope
- [ ] 5.2 Add `?format=csv` export; verify Content-Disposition and filtered row contents
- [ ] 5.3 Add `GET /api/v1/web/churn/analytics/` KPIs, breakdowns, time series, cohorts, leading signals; verify fixture-based analytics numbers
- [ ] 5.4 Add ChurnFollowUp CRUD under `/api/v1/web/churn/follow-ups/`; verify create/list/update/permissions tests
- [ ] 5.5 Wire URLs + OpenAPI; verify schema generation includes new operations

## 6. Dashboard KPIs

- [ ] 6.1 Extend `build_dashboard_summary` with `unsubscribed_this_month`, `churn_rate_this_month`, `at_risk_count`, `won_back_this_month` via shared helpers; verify additive fields and existing keys unchanged
- [ ] 6.2 Update dashboard backend docs and verify documented field meanings match tests

## 7. Integration verification

- [ ] 7.1 Run focused test suites for lifecycle, cancel reason, customer filters, churn APIs, dashboard; verify all new/updated tests pass
- [ ] 7.2 Confirm no N+1 on customer/churn list with assertNumQueries (or equivalent) smoke test for a small fixture set

## Workflow follow-up

- Frontend change `befood-frontend/openspec/changes/admin-unsubscribed-churn` implements UI after this API lands.
- Archive after review when apply is complete.
