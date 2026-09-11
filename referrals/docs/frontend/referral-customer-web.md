# Customer web — referral earnings

## Summary

Customer web should present referral code/link and commission history consistently with mobile. Commission is **not** paid for every referred meal delivery.

**Rule:** Both referrer and referred must be active subscribers, and both must consume the **same meal** (`meal_period`) on the **same `service_date`**. Referrer needs delivery `delivered`; referred needs delivered + charged.

## Headers

```http
Authorization: Token <token>
X-Client-Type: web
```

Do **not** send `referral_code` on web registration (`422`).

## Endpoints

| Action | Method / path |
|--------|----------------|
| My code / stats | `GET /referrals/me/` |
| Share counter | `POST /referrals/me/share/` |
| Referred users | `GET /referrals/me/referred-users/` |
| Commission history | `GET /referrals/me/commissions/` |

## Earnings page UX

1. Show lifetime / month totals from `GET /referrals/me/`.
2. List commissions with `status`, `status_reason`, `meal_service_date`, `meal_period`, `commission_amount`.
3. Empty / skipped states: explain co-consumption; do not imply “any referred meal pays.”
4. If status is `skipped` and reason is `REFERRER_MEAL_NOT_CONSUMED`, tell the user they (or the friend) must take the same meal that day — credit may appear after both complete.

### Example success row

```json
{
  "public_id": "...",
  "status": "success",
  "status_reason": "CREDITED",
  "meal_service_date": "2026-09-10",
  "meal_period": "lunch",
  "commission_amount": "5.00"
}
```

### Example skip row

```json
{
  "status": "skipped",
  "status_reason": "REFERRER_MEAL_NOT_CONSUMED",
  "meal_service_date": "2026-09-10",
  "meal_period": "lunch",
  "commission_amount": "0.00"
}
```

No new required API fields for this change — handle the new `status_reason` value additively.
