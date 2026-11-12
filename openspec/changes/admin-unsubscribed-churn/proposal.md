# Proposal

## Why

Ops can see cancelled subscriptions and “Low Balance Blocked” silent churn on Kitchen Today, but there is no shared lifecycle model, no cancellation reason capture, and no admin churn analytics. With ~46 cancelled subscriptions (median ~28 days tenure) and dozens of at-risk silent churners, admins cannot filter customers by lifecycle, measure churn rate, or run win-back follow-ups.

## What Changes

- Add a **shared lifecycle classification service** (Asia/Dhaka) used by every churn-related endpoint: `active`, `at_risk`, `unsubscribed`, `never_subscribed`, `won_back`.
- Add **`SubscriptionCancellation`** (reason_code required on customer + admin cancel; optional reason_text; `cancelled_by` customer|admin|system). Backfill historical cancels as `reason_code=unknown`. Wire into existing `cancel_subscription` (today `reason` is accepted and ignored).
- Extend **admin customer list** (`GET /api/v1/web/customers/`) with `lifecycle`, churn date range, cancel reason, package filters; enrich rows with lifecycle fields; add churn/tenure sorts. Keep existing filters (`inactive_subscription`, etc.) compatible.
- Add **churn APIs**: paginated unsubscribed list + CSV, analytics KPIs/breakdowns/time series/cohorts/leading signals, and **`ChurnFollowUp`** CRUD.
- Extend **dashboard summary** with monthly unsubscribed, churn rate, at_risk, won_back counts.
- Indexes + unit tests for lifecycle edge cases, filters, and analytics fixtures. **No destructive production data ops.**

**BREAKING (cancel APIs):** Customer `POST .../subscriptions/current/cancel/` and admin cancel MUST require `reason_code`. Clients that omit it get `422`.

## Capabilities

### New Capabilities

- `customer-lifecycle-classification`: Canonical Asia/Dhaka lifecycle rules and queryset annotations shared by list/analytics/dashboard.
- `subscription-cancellation-reason`: Persist and require cancel reasons; system auto-cancels tagged `cancelled_by=system`.
- `admin-churn-customers`: Unsubscribed customer list + CSV export with shared filters.
- `admin-churn-analytics`: Period KPIs, breakdowns, time series, cohort retention, leading signals.
- `churn-follow-up`: Admin win-back follow-up status/notes CRUD.
- `admin-dashboard-churn-kpis`: Additive churn KPIs on dashboard summary.

### Modified Capabilities

- `admin-customer-directory`: Lifecycle/churn filters, enriched list fields, and churn/tenure sort options on the existing customers collection.

## Impact

- **Backend apps:** `orders` (cancel + `SubscriptionCancellation`), `user_management` (customer list, dashboard, churn views), possibly new `churn` package or `orders/services/lifecycle.py` / `user_management/services/churn.py` for shared rules.
- **APIs:** cancel request body; `/api/v1/web/customers/` query/response; `/api/v1/web/churn/*`; `/api/v1/web/dashboard/summary/`.
- **Related in-flight:** `admin-subscription-cancellation` already adds `cancel_source` / `cancelled_by` user FK on `CustomerSubscription` — this change adds a dedicated reason model and does not replace that audit path.
- **Frontend / mobile:** Separate frontend OpenSpec change consumes these contracts; mobile cancel reason is out of this backend change’s UI scope but the API break applies to all cancel clients.
- **Data:** Additive migrations + backfill `unknown` reasons; no deletes of subscription history.
