# Admin Settings — Referral Commission Percent

## Summary

Verified admins manage the **live** referral commission percentage from Admin Settings (`/admin/settings`). The rate applies only to **future** accruals. Existing `ReferralCommission` rows and wallet balances are never rewritten when the percent changes.

## Endpoint

| Method | Path |
|--------|------|
| GET | `/api/v1/web/referrals/settings/` |
| PATCH | `/api/v1/web/referrals/settings/` |

Auth: verified admin (`IsVerifiedAdmin`). Prefer `X-Client-Type: web` and the admin JWT/token used by other settings cards (same as order-wallet-settings).

## Response shape

```json
{
  "referral_commission_percent": "5.00",
  "updated_at": "2026-09-11T00:00:00Z"
}
```

## Update

```http
PATCH /api/v1/web/referrals/settings/
Content-Type: application/json
Authorization: Token <admin-token>
X-Client-Type: web

{
  "referral_commission_percent": "10.00"
}
```

Success: `200` with the updated resource (same shape as GET).

## Validation

| Rule | Allowed | Rejected |
|------|---------|----------|
| Range | `0` … `100` inclusive | `-5`, `150` |
| Decimals | at most 2 places | `10.123` |

Client should block out-of-range input; backend remains authoritative.

## UI placement

On `/admin/settings`, add a **Referral Settings** card (alongside wallet thresholds / meal-off):

1. Load on mount via GET.
2. Show current `%`, editable input, Save.
3. Toast on success/error; show field errors from API.
4. Hint: “Applies to future commissions only. Historical commissions are unchanged.”

## Pattern reference

Mirror `order-wallet-settings`:

- API module → `adminReferralSettingsApi.ts`
- Types → `referralProgramSettingsTypes.ts`
- Hooks → `useAdminReferralSettings.ts`
- Section on `AdminSettingsPage.tsx`

## Financial note

Skipped rows that later upgrade to `success` use the **live** percent at upgrade time (same as accrual). Already-`success` / `reversed` rows keep their snapshot percent/amount.
