## 1. Data model and migration

- [x] 1.1 Add `OrderDelivery` model (`order`, `service_date`, `meal_period`, `status`, `marked_by`, `marked_at`, `note`) with unique constraint on `(order, service_date, meal_period)`
- [x] 1.2 Register `OrderDelivery` in Django admin with list filters useful for ops
- [x] 1.3 Create and apply migration; plan backfill for existing non-cancelled orders

## 2. Delivery generation and lifecycle services

- [x] 2.1 Implement `generate_order_deliveries(order)` with daily=1 slot, weekly/half_monthly/monthly=2×/day (monthly total 60/62)
- [x] 2.2 Hook generation into `create_meal_order` inside the same transaction
- [x] 2.3 Implement lifecycle helpers: activate confirmed→active, complete when daily delivered or all slots terminal / past end date
- [x] 2.4 Implement `mark_delivery(delivery, status, marked_by, note)` with `select_for_update`, idempotency, and daily auto-complete
- [x] 2.5 Add progress helpers (`expected_count`, `delivered_count`, `remaining_count`, `active_days_this_month`)

## 3. Filters and serializers

- [x] 3.1 Extend `OrderFilter` with `activity` (active/inactive), date range filters, and keep meal_type / order_status / order_month
- [x] 3.2 Add delivery + progress fields to customer `OrderDetailSerializer` (read-only, additive)
- [x] 3.3 Add admin list/detail serializers with customer summary and delivery progress
- [x] 3.4 Add mark-delivery request serializer (`status`, optional `note`)

## 4. Admin / web APIs

- [x] 4.1 Add web admin `OrderViewSet` (list/retrieve) under `/api/v1/web/orders/` with pagination and permissions
- [x] 4.2 Add mark-delivery action `POST .../deliveries/{id}/mark`
- [x] 4.3 Optional today-board action filtered by service date / week for kitchen ops
- [x] 4.4 Wire URLs into project web API routing; update OpenAPI helpers

## 5. Customer API polish

- [x] 5.1 Ensure my-orders / retrieve / current-package expose progress counters without allowing mark-delivery
- [x] 5.2 Enforce object ownership (404/403) for other customers’ orders

## 6. Lifecycle sync utility

- [x] 6.1 Add management command or service entrypoint to activate due orders and close expired slots/orders
- [x] 6.2 Document when to run the sync (cron / deploy note)

## 7. Tests

- [x] 7.1 Tests: daily order generates 1 slot and completes after one delivery
- [x] 7.2 Tests: monthly order generates days×2 slots (60/62) and progress counters
- [x] 7.3 Tests: admin list filters (meal_type, activity, order_month) and permission denials
- [x] 7.4 Tests: customer isolation and read-only progress on detail/current-package
- [x] 7.5 Tests: duplicate mark-delivery safety and invalid status transitions

## 8. Documentation

- [x] 8.1 Write `orders/docs/backend/full-order-process.md` (workflows, endpoints, filters, field meanings, status glossary)
- [x] 8.2 Write or update frontend-facing notes under `orders/docs/frontend/` for admin + customer clients
