# Admin Panel Frontend Implementation Prompt (BeFood)

Copy everything below the line into a frontend agent / Cursor chat for `befood-frontend`.

---

You are implementing BeFood **Admin Panel** UI against an already-built Django/DRF backend. Do **not** invent endpoints or field names. Prefer `snake_case` API fields as returned. Auth: `Authorization: Token <admin_token>` on all routes below. Prefer `X-Client-Type: web`. Handle `401` / `403` / `400` / `404` with existing admin error UX. Never show integer DB PKs; always use `public_id` UUIDs.

**Source of truth docs in the backend repo (read these first):**

- `delivery_zones/docs/frontend/zone-based-delivery.md`
- `user_management/docs/frontend/admin-customer-management.md`
- `user_management/docs/frontend/deliveryman-360-analytics.md`
- `user_management/docs/backend/admin-churn.md` (and lifecycle notes in `orders/docs/backend/customer-lifecycle-churn.md`)
- `support/docs/frontend/support-inbox.md`
- `referrals/docs/frontend/referral-admin-panel.md`
- `referrals/docs/frontend/referral-settings-admin.md`
- Planned geo analytics (after backend apply): `delivery_zones/docs/frontend/` geo analytics section + OpenSpec change `add-delivery-geo-analytics-matrix`

Follow the existing Admin Panel design system, routing, React Query patterns, and file layout under `src/features/admin/`. Build pages that feel like one product, not separate demos.

---

## A. Delivery Zones → Location → Sub-location (READY)

**Routes (suggested):** `/admin/delivery-zones` (+ nested location / sub-location management)

**APIs:**

| Area | Base |
|------|------|
| Zones | `/api/v1/web/delivery-zones/` |
| Locations | `/api/v1/web/delivery-locations/` |
| Sub-locations | `/api/v1/web/delivery-sub-locations/` |

**Must build:**

1. Zone CRUD, assign/clear primary delivery man (`PATCH …/{zone}/assign-delivery-man/`), reorder locations, deactivate.
2. Location CRUD under a zone (creating a location creates a **default** sub-location). Reorder sub-locations. Moving a location to another zone cascades customers — show clear confirmation copy.
3. Sub-location CRUD under a location; show `is_default`, priority, status, `customer_count`.
4. Customer assignment UI: `PATCH /api/v1/web/customers/{public_id}/delivery-location/` with `{ "delivery_sub_location_public_id": "<uuid>|null" }`.
   - **Bridge mode** (default backend flag): may also accept legacy `delivery_location_public_id` (maps to default sub). Prefer sub-location in UI.
   - **Contract mode**: location-only assign returns `422` — UI must only send sub-location.
5. Customer list/detail must show nested `delivery_sub_location`, derived `delivery_location`, `delivery_zone`. Filters: `zone_public_id`, `location_public_id`, `sub_location_public_id`, `has_delivery_sub_location`.
6. Ops day board summary: `GET /api/v1/web/delivery-zones/ops/summary/?service_date=YYYY-MM-DD&meal_period=lunch|dinner` — tree Zone → Location → Sub-location counts + `delivery_man_workload` + unassigned counts. This is **live ops for one day/meal**, not multi-day analytics.

---

## B. Delivery Geo Analytics Matrix (BACKEND READY)

**Route (suggested):** `/admin/delivery-zones/analytics` or `/admin/analytics/delivery-geo`

**API (contract from OpenSpec `add-delivery-geo-analytics-matrix`):**

```http
GET /api/v1/web/delivery-zones/analytics/matrix/?from=YYYY-MM-DD&to=YYYY-MM-DD
```

Optional: `meal_period=lunch|dinner`, `zone_public_id`, `location_public_id`, `sub_location_public_id`.

**Timezone:** Asia/Dhaka calendar dates. Max range **366 days**. Missing/invalid → `400`.

**UI requirements:**

1. Date range picker (`from`/`to`) + optional meal period + zone/location/sub-location filters.
2. **Hierarchical matrix table** (expandable): Zone → Location → Sub-location.
   Per node columns (at minimum):
   - Customers: total + lifecycle splits (`active`, `at_risk`, `unsubscribed`, `never_subscribed`)
   - Period churn: `churned_count`, `churn_rate_percent`
   - Meal volume: `scheduled`, `delivered`, `skipped`, `missed`, `total`
   - Zone row: assigned delivery man + period workload
3. **Rankings** panel (same response `rankings` object): highest/lowest customer density, highest churn (min active base 5), highest delivered volume, unassigned customer/delivery totals.
4. **Unassigned** callout: customers/deliveries with no sub-location.
5. **Drill-down actions** on a row:
   - View customers → `/admin/customers?zone_public_id=…` (or location/sub-location / `has_delivery_sub_location=false`)
   - View churned → `/admin/churn/customers?…` + date range + geo if filters exist; otherwise open churn list with `churned_from`/`churned_to` and note geo filter via customer list
6. Empty states when no zones or all zeros. Do not invent placeholder numbers.
7. Clearly label this page **“Period analytics”** vs ops summary **“Today / meal ops”**.

**Attribution note to show in UI help text:** customer/churn geo uses **current** assignment; meal volume prefers logistics sub-location then customer sub-location.

Wire the real GET above. Contract details: `delivery_zones/docs/frontend/delivery-geo-analytics.md`.

---

## C. Churn / Unsubscribed Admin (READY / in progress on backend)

**Routes (suggested):** `/admin/churn`, `/admin/churn/customers`, `/admin/churn/analytics`, `/admin/churn/follow-ups`

**APIs:**

| Method | Path |
|--------|------|
| GET | `/api/v1/web/churn/customers/` (default `lifecycle=unsubscribed`; `?format=csv` export) |
| GET | `/api/v1/web/churn/analytics/?from=&to=` |
| GET/POST | `/api/v1/web/churn/follow-ups/` |
| GET/PATCH | `/api/v1/web/churn/follow-ups/{public_id}/` |

**Must build:**

1. Unsubscribed customer table with filters: `lifecycle`, `churned_from`, `churned_to`, `cancel_reason`, `package`, `q`, `sort`.
2. Row fields: identity, lifecycle, package, churn date, tenure, meals delivered, cancel reason, wallet, follow-up status.
3. Analytics dashboard for date range: KPIs (churned count, churn rate, net growth, win-back, at_risk, never_subscribed, tenure, revenue lost), breakdowns, time series, cohorts, leading signals.
4. Follow-up CRM statuses: `not_contacted`, `contacted`, `interested`, `won_back`, `lost`.
5. Dashboard cards on admin home from `GET /api/v1/web/dashboard/summary/`: `unsubscribed_this_month`, `churn_rate_this_month`, `at_risk_count`, `won_back_this_month`.

Lifecycle values: follow backend docs (`active`, `at_risk`, `unsubscribed`, `never_subscribed`, etc.).

---

## D. Customer directory (READY — extend for geo)

**Route:** existing `/admin/customers`

Ensure list filters and detail show delivery hierarchy (A). Deep-links from geo analytics (B) and churn (C) must land with query params applied.

---

## E. Delivery Man 360 (READY)

Use `user_management/docs/frontend/deliveryman-360-analytics.md`. Admin Delivery Men profile: overview, today/month/lifetime, history, timeline, route, ranking. Link from zone assign UI.

---

## F. Support Inbox (READY)

Use `support/docs/frontend/support-inbox.md`.

- List: `GET /api/v1/web/support/conversations/`
- Thread + WebSocket live messaging; REST fallback send
- Unread, typing, presence; no delete; text-only v1

---

## G. Referrals admin (READY)

Use `referrals/docs/frontend/referral-admin-panel.md` + settings doc.

- Settings, analytics funnel (note Valid OK vs registrations semantics), relationships, commissions, reverse, adjustments
- Show co-consumption eligibility rule in UI help (both active subs; referred delivered+charged; referrer matching meal delivered)

---

## Implementation order (recommended)

1. Delivery Zones + Sub-locations + customer assign (A) — if not already done  
2. Ops summary day view (A.6)  
3. Churn list + analytics + follow-ups + dashboard KPIs (C)  
4. Geo analytics matrix page (B) — after backend `/analytics/matrix/` is live  
5. Polish drill-downs between B ↔ customers ↔ churn  
6. Support inbox / referrals only if those admin routes are still missing  

## QA checklist

- [ ] Bridge vs Contract sub-location assign behavior  
- [ ] Cascade copy when moving location between zones  
- [ ] Ops summary requires `service_date` + `meal_period`  
- [ ] Geo matrix requires `from` + `to`; rejects >366 days  
- [ ] Rankings hide noisy churn when active base < 5  
- [ ] Unassigned customers visible and filterable  
- [ ] No fake zeros that look like real data in empty states  
- [ ] All links use `public_id`  

Build production-ready Admin Panel pages with loading/error/empty states, pagination where the API paginates, and types matching the backend docs. If an endpoint 404s, say so and point to the backend doc path instead of inventing a mock contract.