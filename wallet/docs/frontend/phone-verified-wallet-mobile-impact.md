# Mobile impact: phone-verified wallet access

Backend change: `phone-verified-wallet-access`.

## Goal

Phone OTP–registered customers must be able to recharge / withdraw without email verification. Email remains optional for phone accounts.

## Backend contract (already / after deploy)

| Signal | Meaning |
|--------|---------|
| `verification_status.identity_verified` | Any trusted factor (phone / email / Google / Facebook) |
| `verification_status.phone_verified` | Phone OTP completed |
| `verification_status.email_verified` | Email verified (optional for phone users) |

Customer wallet endpoints use `IsVerifiedWalletCustomer` (same OR-rule as other customer features).

Identity `403` English detail:

```text
Identity verification is required before accessing your wallet.
```

**Recommended Bangla UI:** `ওয়ালেট ব্যবহার করতে আগে পরিচয় যাচাই করুন (ফোন OTP)।`  
Do **not** map this to “ইমেইল ভেরিফাই করুন” for phone-registered users.

## Mobile checklist

1. **Remove email hard-gate before recharge** — if the app blocks “Submit recharge” when email is missing/unverified, remove that check.
2. **Allow funding when** `identity_verified === true` **or** `phone_verified === true` (prefer `identity_verified`).
3. **Auth / `/me` parsing** — keep per-provider flags; drive gates from `identity_verified`.
4. **403 mapping** — update string matchers if they key off old order-placement copy (`…before placing an order`) or “Email verification is required…”.
5. **Soft email upsell only** — optional banner to add email for recovery; never block wallet funding for phone-verified users.

## When is a mobile release mandatory?

| App behavior today | Action |
|--------------------|--------|
| Already trusts backend; no client email-must-verify before recharge | **No mandatory code change** — optional copy polish for new `403` text |
| Blocks recharge until email verified | **Required** — remove gate and ship with backend deploy |
| Shows Bangla “verify email” for any identity `403` | **Required** — update copy to identity/phone wording |

## Smoke after backend deploy

1. Phone OTP register → login → `GET /wallet/` → `200`.
2. `POST /wallet/recharge/` with amount + method + transaction id → `200` pending (not identity `403`).
3. Completely unverified customer → `403` with wallet identity message above.
