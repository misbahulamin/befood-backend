## 1. Target-month period & order create

- [x] 1.1 Extend `calculate_order_period` (or add wrapper) to accept target `(year, month)`: current month keeps `localdate()` reference; future months use day-1 of that month; always stamp `order_month` as selected `YYYY-MM`
- [x] 1.2 Add shared validators for allowed meal-month window (current … +12) and paired `year`/`month` presence
- [x] 1.3 Update `create_meal_order` to accept optional `year`/`month`, compute period for that target, then run publish gate → month lock → wallet min → create
- [x] 1.4 Add `MenuNotPublishedError` (or equivalent) with stable customer message; wire through `OrderCreateSerializer` like other domain errors
- [x] 1.5 Extend `OrderCreateSerializer` with optional `year`/`month`; omit = current-month backward-compatible path

## 2. Orderable months API

- [x] 2.1 Implement service to build 13 month entries (`year`, `month`, `order_month`, `label`, `is_current`, `is_published`, `has_order`) using `published_schedule_for_meal` and caller’s non-cancelled orders
- [x] 2.2 Add verified-customer `GET` endpoint (e.g. `/orders/orderable-months/?meal_public_id=`) with 401/404 handling
- [x] 2.3 OpenAPI examples for success and error cases

## 3. Order-menu preview API

- [x] 3.1 Implement preview builder reusing package-menu slot/ingredient shaping (visibility + plan-line roles) keyed by `meal_public_id` + year/month without requiring an order
- [x] 3.2 Add verified-customer `GET /meals/order-menu-preview/` (`meal_public_id`, `year`, `month`); unpublished → `200` with `schedule_published: false` and empty days
- [x] 3.3 OpenAPI for preview; leave `my-package-menu` ownership-scoped behavior unchanged

## 4. Tests

- [x] 4.1 Period helper: current vs future month; window bounds; monthly full-month dates for a future target
- [x] 4.2 Order create: future published month succeeds with correct `order_month`; omit year/month still works; past / >+12 / partial year-month rejected
- [x] 4.3 Publish gate: unpublished rejects create; published + lock + wallet pass
- [x] 4.4 Month lock per selected month; wallet min still enforced; existing other-month order does not block
- [x] 4.5 Orderable-months: 13 entries, `is_current`, publish/`has_order` flags, auth/404
- [x] 4.6 Order-menu preview: published content without order; unpublished empty; invalid query; auth/404; `my-package-menu` still empty without order

## 5. Documentation

- [x] 5.1 Backend docs under `orders/docs/backend/future-month-meal-ordering.md` (eligibility order, period rules, endpoints)
- [x] 5.2 Frontend integration guide under `orders/docs/frontend/future-month-meal-ordering.md`: month picker UX (default current), API sequence (orderable-months → preview → create), field dictionary, request/response examples, unpublished message (EN + BN for UI copy), error cheat sheet, wallet + month-lock integration
- [x] 5.3 Cross-link from meals package-menu frontend doc if preview lives under meals URLs
