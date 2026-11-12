# Admin churn APIs

## Quick summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/web/churn/customers/` | Paginated unsubscribed (default) / lifecycle-filtered customers |
| GET | `/api/v1/web/churn/customers/?format=csv` | CSV export of filtered set |
| GET | `/api/v1/web/churn/analytics/?from=&to=` | Period KPIs, breakdowns, time series, cohorts, leading signals |
| GET/POST | `/api/v1/web/churn/follow-ups/` | List / create win-back follow-ups |
| GET/PATCH | `/api/v1/web/churn/follow-ups/{public_id}/` | Retrieve / update follow-up |

Auth: verified admin (`IsVerifiedAdmin`). `401` / `403` otherwise.

Lifecycle rules: `orders/docs/backend/customer-lifecycle-churn.md`.

## Customers list

Default scope: `lifecycle=unsubscribed`. Shared filters: `lifecycle`, `churned_from`, `churned_to`, `cancel_reason`, `package`, `q`, `sort` (`churn_date`, `-churn_date`, tenure aliases, existing customer sorts).

Row fields include: identity, `lifecycle`, `last_subscription_package`, `churn_date`, `tenure_days`, `total_meals_delivered`, `last_cancel_reason`, `wallet_balance`, follow-up status.

## Analytics

Required `from` / `to` (`YYYY-MM-DD`, Asia/Dhaka, max 366 days). Missing/invalid → `400`.

KPIs use unique customers for churn rate denominator (active at period start).

## Follow-ups

Statuses: `not_contacted`, `contacted`, `interested`, `won_back`, `lost`.

## Dashboard additive fields

`GET /api/v1/web/dashboard/summary/` also returns:

- `unsubscribed_this_month`
- `churn_rate_this_month`
- `at_risk_count`
- `won_back_this_month`

## How to verify

```bash
python manage.py test orders.tests.test_customer_lifecycle orders.tests.test_subscription_cancellation_reason user_management.tests.test_admin_churn -v2
```
