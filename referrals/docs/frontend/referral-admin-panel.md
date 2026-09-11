# Admin panel — referral commissions

## Summary

Admins review relationships, commissions, analytics, reverse, and manual adjustments. After the co-consumption eligibility fix, **referred meal delivered alone is not enough**.

## Rule for support

Commission succeeds only when:

1. Both parties have an **active** meal subscription.
2. Referred meal is **delivered + charged**.
3. Referrer has a **matching** meal (`same service_date` + `same meal_period`) with status **delivered** (referrer does **not** need to be charged).

If the referred meal completes first, expect a `skipped` row with `REFERRER_MEAL_NOT_CONSUMED`. When the referrer later delivers the matching meal, the **same** commission row upgrades to `success` (one delivery = one lifecycle).

## Endpoints

| Action | Path |
|--------|------|
| Settings (commission %) | `GET\|PATCH /api/v1/web/referrals/settings/` |
| Analytics | `GET /api/v1/web/referrals/analytics/` |
| Relationships | `GET /api/v1/web/referrals/relationships/` |
| Commissions | `GET /api/v1/web/referrals/commissions/` |
| CSV export | `GET /api/v1/web/referrals/commissions/export/` |
| Reverse | `POST /api/v1/web/referrals/commissions/{id}/reverse/` |
| Manual adjust | `POST /api/v1/web/referrals/adjustments/` |

Auth: verified admin. Prefer `X-Client-Type: web`.

Commission percent for Admin Settings UI: see `referral-settings-admin.md`.

## Investigating a missing commission

1. Confirm a `ReferralRelationship` exists for the referred customer.
2. Confirm referred delivery is `delivered` + `charged` for that date/period.
3. Confirm referrer has an active subscription.
4. Confirm referrer has a **delivered** delivery for the **same** `service_date` + `meal_period` (meal-off / different meal → no pay).
5. Read `status` / `status_reason` on the commission list (`REFERRER_MEAL_NOT_CONSUMED`, inactive reasons, float failure).

## Historical SUCCESS

Commissions credited under the older rule (referred meal only + dual active sub) may remain `success` after deploy. They are **not** auto-clawed back. Use reverse or an approved finance one-off if required.

## Ops: reconcile dry-run

Before production write reconcile / cron:

```bash
python manage.py reconcile_referral_commissions --dry-run --limit 100
```

Review planned backfills/upgrades, then run without `--dry-run`. Blind reconcile on the money path is risky.

## UI tips

- Show `status_reason` tooltip/filter on commission tables.
- Document reverse reason required.
- Clarify complimentary referrer meals (`delivered` without charge) still count for eligibility.
