## Why

Verified admins can approve Delivery Men and assign zones, and riders can mark meal slots delivered on the mobile board — but admins have no per-rider 360° performance view. Ops today only expose count aggregates for a single `service_date` + `meal_period`. There is no durable rider-on-stop attribution, lifecycle timestamps (accept / pick / out-for-delivery), completion GPS, duration, timeline, route sequence, or ranking. Without this, supervisors cannot answer “how is Rahim doing today / this month / lifetime?” from one admin screen.

## What Changes

- **Admin Delivery Man 360 dashboard APIs** (verified-admin, web-only): list with performance KPIs, lean profile overview, today / month / lifetime metrics, paginated delivery history with filters, activity timeline, route sequence for a meal window, and cross-rider ranking/comparison
- **Logistics tracking on top of meal slots**: capture richer completion and status-transition data when riders (and admins) progress a stop — without replacing `OrderDelivery` meal fulfillment statuses (`scheduled` / `delivered` / `skipped` / `missed`)
- **Durable rider attribution**: persist which Delivery Man fulfilled each stop (zone reassignment must not rewrite history)
- **Activity log + optional daily summary**: append-only status events with timestamps (and optional lat/lng); pre-aggregated daily KPIs for fast dashboards
- **Mobile mark enrichment** (additive): allow optional GPS and intermediate logistics transitions where product enables them; keep existing `POST .../mark/` with `status=delivered` working
- **Frontend contract docs** for Admin Panel → Delivery Men → Profile → 360 Analytics (Overview, Today/Month/Lifetime, History, Timeline, Route Map, Ranking)
- **No customer-facing API changes**; Delivery Man login and today-board remain the primary rider UX
- Not **BREAKING** for existing meal mark or admin approve/assign-zone contracts (additive fields and new sub-resources)

## Capabilities

### New Capabilities

- `admin-deliveryman-360`: Verified-admin APIs for Delivery Man list KPIs, analytics overview, filtered/paginated delivery history, timeline, route sequence, and ranking/comparison
- `deliveryman-logistics-tracking`: Rider logistics status lifecycle, activity log, completion capture fields (timestamps, GPS, duration), and daily summary aggregates tied to `OrderDelivery` stops
- `admin-deliveryman-360-frontend-docs`: Frontend page structure, field mappings, filters, and empty-state guidance for the Delivery Man 360 admin UI

### Modified Capabilities

- `deliveryman-admin-management`: Extend admin list/detail overview with assigned zone, availability, joining date, and summary delivery counts (today / month / lifetime) used as entry points into 360 analytics
- `order-delivery-tracking`: Additive requirements for mark/completion paths to persist logistics audit fields and activity events when a stop is completed (or transitions logistics state), without changing meal-slot status vocabulary for skip/miss

## Impact

- **Backend (`befood-backend`)**:
  - Models / migrations: extend live path around `orders.OrderDelivery` + new logistics/activity/summary tables (prefer not resurrecting unmounted `delivery.DeliveryAssignment` as the source of truth)
  - Services: new admin analytics services; extend `orders/services/order_delivery.py` mark path; optional deliveryman board transition helpers in `delivery_zones/`
  - APIs: new `/api/v1/web/...` admin deliveryman analytics routes (alongside existing `/user_management/admin/deliverymen/` approve/assign flows); additive mobile mark payload fields under `/user_management/deliveryman/`
  - Permissions: `IsVerifiedAdmin` for admin 360; `IsVerifiedDeliveryman` for rider transitions
  - Tests + OpenAPI + backend docs
- **Existing domains reused**: `RiderProfile`, `DeliveryZone` / `DeliveryLocation`, `OrderDelivery`, zone ops summary patterns, admin-customer-360 lean-overview + lazy sub-resource pattern
- **Frontend (`befood-frontend`)**: new Admin Delivery Men analytics pages (documented here; implementation tracked via frontend-docs capability — backend ships API contract first)
- **Out of scope for this change**: live GPS streaming / continuous map tracking, customer-facing delivery ETA, payroll/payout for riders, replacing zone-based assignment with per-stop dispatch, mounting legacy `delivery` app URLs
- **Performance**: history/timeline MUST be paginated; dashboards SHOULD prefer daily summary tables or indexed aggregates over full-table scans of lifetime deliveries
