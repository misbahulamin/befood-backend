# Mobile referral integration

## Summary

Mobile apps can validate a referral code, pass it during registration, and show the signed-in user’s code/link/earnings. Commission lands in `commission_balance` (spendable on meals, **not** withdrawable).

**Important:** Commission is **not** earned on every referred meal. Both users must have an active meal subscription, and both must **consume the same meal type on the same day** (referrer `delivered`; referred `delivered` + charged).

## Headers

```http
Authorization: Token <token>
X-Client-Type: mobile
```

Web clients must **not** send `referral_code` (backend returns `422`).

## Registration (mobile only)

Optional body field on:

- `POST /user_management/customer/register/` (stored on pending; applied at email finalize)
- `POST /user_management/phone/otp/verify/`
- `POST /user_management/oauth/google/`
- `POST /user_management/oauth/facebook/`

```json
{
  "referral_code": "BEF8A92KX"
}
```

Inactive referrer error detail includes:

`Your referrer does not have an active meal subscription.`

## Validate before signup

`POST /referrals/validate/`

```json
{ "referral_code": "BEF8A92KX" }
```

Success: `{ "valid": true, "referral_code": "...", "referrer_public_id": "..." }`  
Rate limit: HTTP `429` when IP exceeds `REFERRAL_VALIDATE_RATE`.

**Validate is not attribution.** A successful validate only checks that the code is usable and records an analytics event. It does **not** create a `ReferralRelationship`.

### Persist-until-create checklist

1. Read `referral_code` from deep link / invite URL / validate response.
2. Persist it in secure local storage until the **first successful brand-new customer create**.
3. Send `referral_code` again on register / phone verify / oauth with header `X-Client-Type: mobile`.
4. Do not clear the stored code after validate alone.
5. Clear the stored code only after create succeeds (or after an existing-login path where referral is ignored).

### Auth success envelope (additive)

When a non-empty `referral_code` was present on a brand-new create path, success bodies may include:

```json
{
  "referral_attributed": true,
  "referral_status_reason": null
}
```

Email finalize can still create the account when attribution fails closed:

```json
{
  "referral_attributed": false,
  "referral_status_reason": "REFERRER_INACTIVE"
}
```

Phone/OAuth hard-fail on referral errors (HTTP 400) instead of silent skip.

## After login

1. `GET /referrals/me/` — code, link, `is_usable`, stats  
2. `POST /referrals/me/share/` — increments share counters  
3. `GET /referrals/me/referred-users/` — paginated  
4. `GET /referrals/me/commissions/` — paginated history with `status` + `status_reason`

## Commission eligibility (show on earnings / share UI)

Recommended helper copy (EN):

> You earn commission when you and your referred friend both take the same meal on the same day, and both have an active subscription.

Suggested BN product copy should be confirmed with localization.

### Screens

| Screen | What to show |
|--------|----------------|
| Referral share | Short eligibility one-liner (not “earn on every friend meal”) |
| Earnings / commission history | `status` + mapped `status_reason` |
| Empty history | Explain co-consumption; pending friend meals may appear as skipped until you also take that meal |

### `status_reason` → UI guidance

| `status_reason` | Suggested user-facing meaning |
|-----------------|-------------------------------|
| `CREDITED` / status `success` | Commission credited |
| `REFERRER_MEAL_NOT_CONSUMED` | You did not take the same meal that day (may credit later if you do) |
| `REFERRER_INACTIVE` | Your subscription was not active |
| `REFERRED_INACTIVE` | Friend’s subscription was not active |
| `AMOUNT_TOO_SMALL` | Amount too small to credit |
| `ADMIN_FLOAT_INSUFFICIENT` | Temporary failure; may retry |
| `REVERSED` / `MANUAL_ADJUSTMENT` | Admin adjustment |

API fields already include `meal_service_date`, `meal_period`, `commission_amount` — no breaking schema change for this eligibility fix.

## Wallet buckets

`GET /wallet/` now includes:

- `balance` — total spendable  
- `recharge_balance` / `withdrawable_balance` — withdrawable  
- `commission_balance` — referral earnings (not withdrawable)

Withdraw API rejects amounts above `recharge_balance` even if total `balance` is higher.
