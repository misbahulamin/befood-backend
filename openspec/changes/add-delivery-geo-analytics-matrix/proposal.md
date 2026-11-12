# Proposal

## Why

Ops can already see **one day / one meal period** delivery counts (`ops/summary`) and global churn KPIs, but growth decisions need a **geo matrix**: which zone, location, and sub-location have dense vs thin customers, where unsubscribes concentrate, how many meals move through each area, and which rider owns the load. Without backend analytics sliced by Zone → Location → Sub-location over a date range, admins cannot prioritize expansion, rider capacity, or win-back by area.

## What Changes

- Add verified-admin **delivery geo analytics** APIs that return a hierarchical matrix and flat ranked tables for a required date range (`from` / `to`, Asia/Dhaka).
- Per geo node (zone / location / sub-location), expose **customer stock** (assigned customers, lifecycle splits: active / at_risk / unsubscribed / never_subscribed where attributable), **period churn** (unsubscribes + churn rate vs active base in that node), **meal delivery volume** (scheduled / delivered / skipped / missed, optional lunch vs dinner), and **rider attribution** (primary zone delivery man + period workload).
- Expose **comparative / ranking** views: highest and lowest customer density, highest churn, highest meal volume, unassigned (no sub-location) customers and deliveries.
- Keep existing day-scoped `GET …/delivery-zones/ops/summary/` unchanged for live ops; geo analytics covers multi-day business analysis.
- Ship backend + frontend contract docs so Admin Panel can render heatmaps/tables without guessing field meanings.
- Not **BREAKING**: additive web endpoints and docs only.

## Capabilities

### New Capabilities

- `admin-delivery-geo-analytics`: Verified-admin date-range analytics matrix and rankings for Zone → Location → Sub-location covering customer lifecycle density, churn, meal delivery volume, and delivery-man workload.
- `admin-delivery-geo-frontend-docs`: Frontend integration contract for Admin Panel geo analytics screens (filters, matrix columns, drill-down, empty states, links into customer/churn lists).

### Modified Capabilities

- `admin-customer-directory`: Document and preserve allowlisted geo filters (`zone_public_id`, `location_public_id`, `sub_location_public_id`, `has_delivery_sub_location`) as the drill-down target from matrix rows (no breaking filter changes).

## Impact

- **Apps:** `delivery_zones` (new analytics services + web views/urls, tests, docs); likely reuse of `orders` (`OrderDelivery`, subscription cancel dates), `user_management` / `orders.services.customer_lifecycle` (lifecycle classification), and patterns from `user_management.services.churn` (period bounds, churn rate).
- **APIs:** New web routes under `/api/v1/web/delivery-zones/analytics/…` (or equivalent documented prefix); existing ops summary and churn analytics remain.
- **Clients:** Admin Panel only (`IsVerifiedAdmin`); not for mobile riders.
- **Non-goals:** GPS heatmaps / map tiles, payroll, changing zone assignment rules, replacing day ops summary, implementing React UI inside this backend repo (docs + a copy-paste frontend prompt for the customer), CSV export in v1 (may follow later).
