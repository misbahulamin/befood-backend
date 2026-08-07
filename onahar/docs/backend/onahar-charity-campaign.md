# Backend: Onahar Charity Campaign

## Quick summary

Onahar turns eligible **delivered meal slots** into monthly charity contributions. Every N delivered meals (admin-configurable target, default **50**) become **1 Onahar meal** in a ledger-backed fund. Admins publish distribution campaigns that debit the fund. Public APIs expose transparent stats without PII.

| Area | Base path | Auth |
|------|-----------|------|
| Public | `/onahar/` | None |
| Customer | `/onahar/me/` | Token + verified customer |
| Admin | `/api/v1/web/onahar/` | Token + verified admin |

Feature flag: `ONAHAR_ENABLED` (default `True`).

## Permissions matrix

| Caller | Public | Customer me/* | Admin web |
|--------|--------|---------------|-----------|
| Anonymous | yes | 401 | 401 |
| Customer | yes | own data only | 403 |
| Verified admin | yes | (if also customer) | yes |

## Key models

- `OnaharSettings` (pk=1): target + denormalized fund totals
- `OnaharTargetHistory`: target change audit
- `OnaharMonthlyProgress`: per customer + `YYYY-MM`, `target_snapshot`, points, status `open|closed`
- `OnaharPointEvent`: unique `(order_delivery, event_type)` credit/reverse
- `OnaharContribution`: earned (+1) or adjustment (−1)
- `OnaharFundLedgerEntry`: append-only meal credits/debits
- `OnaharDistribution` + `OnaharDistributionMedia`
- `OnaharPrivacyPreference`: `public|partial|anonymous` (default `partial`)
- `OnaharAuditLog`

## Business rules

1. **Eligible unit** = `OrderDelivery` with status `delivered` (not package order create).
2. **1 delivery = 1 point** (idempotent per delivery).
3. **Month** = service date `YYYY-MM` (project `TIME_ZONE=Asia/Dhaka`).
4. Contributions = `floor(net_points / target_snapshot)`; remainder does **not** carry to next month.
5. Target changes do **not** rewrite existing monthly snapshots.
6. Publish distribution requires `meals <= available`; cancel published restores fund.
7. Refunds/undos call `reverse_for_delivery` (service ready; wire when refund path ships).

## Hooks & jobs

- **Credit hook:** `orders.services.order_delivery.mark_delivery` → `credit_for_delivery` after successful deliver (+ wallet charge).
- **Reverse helper:** `onahar.services.hooks.onahar_on_delivery_reversed(delivery)`.
- **Month close:** `python manage.py close_onahar_month [--month YYYY-MM]`  
  Cron suggestion (1st of month 00:15 Asia/Dhaka): close previous month.
- **Reconcile:** `python manage.py reconcile_onahar_points [--dry-run]`

## Endpoint grid

### Public

- `GET /onahar/stats/`
- `GET /onahar/leaderboard/`
- `GET /onahar/ledger/`
- `GET /onahar/distributions/`
- `GET /onahar/distributions/{public_id}/`

### Customer

- `GET /onahar/me/`
- `GET /onahar/me/history/`
- `GET|PATCH /onahar/me/privacy/`

### Admin

- `GET|PATCH /api/v1/web/onahar/settings/`
- `GET /api/v1/web/onahar/settings/history/`
- `GET /api/v1/web/onahar/fund/`
- `GET /api/v1/web/onahar/audit-logs/`
- `GET|POST /api/v1/web/onahar/distributions/`
- `GET|PATCH /api/v1/web/onahar/distributions/{public_id}/`
- `POST .../publish/`, `POST .../cancel/`, `POST .../media/`

## Errors

| Situation | Status | Notes |
|-----------|--------|-------|
| Over-fund publish | 409 | `INSUFFICIENT_ONAHAR_FUND` |
| Edit non-draft | 409 | `DISTRIBUTION_NOT_DRAFT` |
| Invalid target / privacy | 400 | validation |
| Unauthenticated | 401 | |
| Forbidden | 403 | |

## How to verify

```bash
python manage.py migrate onahar
python manage.py test onahar.tests.test_onahar
```

OpenSpec: `openspec/changes/onahar-charity-campaign/`.
