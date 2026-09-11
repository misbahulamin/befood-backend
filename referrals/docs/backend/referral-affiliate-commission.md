# Referral / Affiliate Commission

## Quick summary

Active meal subscribers share a permanent `BEF########` referral code. Mobile signups can attribute to that code. The referrer earns a configurable commission (default 5%) into a **non-withdrawable** wallet commission bucket, funded by debiting the platform Admin Wallet — **only when both parties are active subscribers and both consume the same meal on the same day**.

| Area | Path |
|------|------|
| Customer me | `GET /referrals/me/` |
| Share counter | `POST /referrals/me/share/` |
| Referred users | `GET /referrals/me/referred-users/` |
| My commissions | `GET /referrals/me/commissions/` |
| Validate code | `POST /referrals/validate/` (IP throttled) |
| Admin analytics | `GET /api/v1/web/referrals/analytics/` |
| Admin lists / CSV | `/api/v1/web/referrals/relationships/`, `/commissions/`, `/commissions/export/` |
| Admin reverse / adjust | `POST .../commissions/{id}/reverse/`, `POST .../adjustments/` |
| Admin settings | `GET|PATCH /api/v1/web/referrals/settings/` |

## Permissions

| Endpoint | Auth |
|----------|------|
| Customer referral APIs | Verified customer profile |
| Validate | Public + IP throttle (`REFERRAL_VALIDATE_RATE`) |
| Admin APIs | Verified admin |

## Settings

- `REFERRAL_ENABLED` (default True) — feature flag
- `REFERRAL_COMMISSION_PERCENT` (default `5`) — **seed / fallback only** when creating the singleton `ReferralProgramSettings` row
- **Live rate:** `ReferralProgramSettings.commission_percent` via `GET|PATCH /api/v1/web/referrals/settings/` (verified admin). Changing the percent applies to **future** accruals only; historical `ReferralCommission` rows and wallets are not rewritten.
- `REFERRAL_LINK_BASE_URL`
- `REFERRAL_VALIDATE_RATE` (default `30/hour`)

## Models

- `ReferralProfile` — unique code, optional `share_count` / `last_shared_at`
- `ReferralRelationship` — immutable one referrer per referred (mobile)
- `ReferralCommission` — statuses: `pending`, `success`, `failed`, `skipped`, `reversed` (stores snapshot `commission_percent` / `commission_amount`)
- `ReferralProgramSettings` — singleton live commission percent (0–100)
- `ReferralValidationEvent` — conversion analytics from validate API

## Commission eligibility (co-consumption)

Rule:

> A referrer earns commission from a referred customer’s meal only when both are active subscribers and both consume the exact same meal (`service_date` + `meal_period`) on the same day.

| Party | Required |
|-------|----------|
| Referred | Active subscription + `OrderDelivery` `delivered` **and** `payment_status=charged` (amount basis) |
| Referrer | Active subscription + matching `OrderDelivery` `status=delivered` for same date/period (**not** required to be charged) |

### Flow

1. Referred meal marked delivered and charged (`mark_delivery`) → primary accrual attempt.
2. If referrer already delivered the same meal → credit `success`.
3. If referrer has not → persist `skipped` / `REFERRER_MEAL_NOT_CONSUMED` (retryable).
4. When referrer later marks matching meal delivered → secondary pass upgrades **the same** commission row in place: `skipped` → `success`.
5. Reconcile can also upgrade retryable skips after both meals qualify.

### Machine-readable `status_reason` (common)

| Reason | Meaning |
|--------|---------|
| `REFERRER_INACTIVE` | Referrer has no active subscription |
| `REFERRED_INACTIVE` | Referred has no active subscription |
| `REFERRER_MEAL_NOT_CONSUMED` | Referrer missing same-day same-period delivered meal (retryable) |
| `AMOUNT_TOO_SMALL` | Rounded commission &lt; 0.01 |
| `ADMIN_FLOAT_INSUFFICIENT` | Admin Wallet could not cover debit (`failed`) |
| `CREDITED` | Success |

## Business rules

1. Code usable only while referrer has active `CustomerSubscription`.
2. Attribution only with `X-Client-Type: mobile`; web + code → `422`.
3. Pending email signup stores `referral_code` + `referrer_snapshot_id`; **finalize re-checks** eligibility.
4. Commission hooks in `mark_delivery` after wallet charge (primary + secondary referrer unlock).
5. Dual active subscription + co-consumption required; else `skipped` (or no row if no relationship).
6. One referred delivery = one non-manual commission lifecycle; meal-mismatch skips upgrade **in place**.
7. Admin float shortfall → `failed` (no user credit; reconcile later).
8. Wallet: `balance = recharge_balance + commission_balance`; withdraw only from recharge; meal debit burns commission first.
9. Historical `success` rows created under the older looser rule are **not** auto-reversed; use admin reverse / approved one-off for clawback.
10. Ledger completed rows store `balance_after`, `recharge_balance_after`, `commission_balance_after`.

## Index / lookup note

Referrer meal lookup prefers `subscription` + `service_date` + `meal_period` (unique constraint on `OrderDelivery`) and asserts `status=delivered`. Existing indexes `(service_date, status)`, `(subscription, status)` plus that unique constraint are sufficient for the chosen path; no extra composite index was added without a measured need.

## Ops commands

```bash
python manage.py migrate
python manage.py verify_wallet_balance_consistency
python manage.py backfill_referral_profiles

# Always dry-run first in production (no money writes):
python manage.py reconcile_referral_commissions --dry-run --limit 100

# Then write run / cron only after reviewing dry-run output:
python manage.py reconcile_referral_commissions --limit 100
```

## Future (not enforced in v1)

Same-phone / device-id / email-domain fraud heuristics may be added later; schema room is reserved via events/metadata, not enforced.

## Rollout checklist

1. Migrate wallet dual buckets → run `verify_wallet_balance_consistency`
2. Migrate referrals → `backfill_referral_profiles`
3. Enable attribution (`REFERRAL_ENABLED`)
4. Confirm Admin Wallet float for commissions
5. Deploy co-consumption eligibility; run `reconcile_referral_commissions --dry-run` before write cron
6. Monitor reverse/adjust admin actions; do not auto-clawback historical SUCCESS
