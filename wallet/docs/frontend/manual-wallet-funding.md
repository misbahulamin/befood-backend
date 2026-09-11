# Customer Wallet Funding — Frontend Integration

Manual off-platform verification. Frontend shows bKash/Nagad/Bank payment instructions; backend stores the selected method + transaction id and waits for admin approval.

## Auth

- Customer: **identity-verified** customer token (`Authorization: Token …` or project JWT as used elsewhere). Identity = phone **or** email **or** social — email is **not** required for phone OTP accounts.
- Admin: verified admin / superuser (`IsVerifiedAdmin`).

Optional: `Idempotency-Key` header (or body `idempotency_key`) on create.

### Identity denial (`403`)

English API detail:

```text
Identity verification is required before accessing your wallet.
```

Mobile Bangla: tell users to complete phone/identity verification — **not** “verify email first” for phone-registered users. Full mobile checklist: `phone-verified-wallet-mobile-impact.md`.

## Customer endpoints

Base: `/wallet/`

### `POST /wallet/recharge/`

Creates a **pending** recharge. Balance does **not** increase until admin approve.

Phone-verified customers may submit this without email verification.

```json
{
  "amount": "500.00",
  "payment_method": "bkash",
  "transaction_id": "TX123456",
  "note": "optional"
}
```

`payment_method`: `bkash` | `nagad` | `bank` (not `manual`).

API field `transaction_id` maps to ledger `external_ref`.

### Provider `transaction_id` uniqueness

| Prior recharge status | Same method + `transaction_id` |
|-----------------------|--------------------------------|
| `pending` | **Blocked** (409 duplicate) |
| `completed` (approved) | **Blocked** (409 duplicate) |
| `failed` (rejected) | **Allowed** — customer may resubmit |
| `cancelled` | **Allowed** |

Reject does **not** clear `external_ref` (kept for audit). Only live `pending`/`completed` rows occupy the unique slot.

### `GET /wallet/`

Returns dual-bucket balances and thresholds. Important fields:

| Field | Meaning |
|-------|---------|
| `balance` | Total spendable |
| `recharge_balance` | Full recharge bucket |
| `commission_balance` | Non-withdrawable commission |
| `meal_stop_threshold` | From order wallet settings |
| `withdrawable_balance` | **Maximum withdrawable** = `max(0, recharge_balance − meal_stop_threshold)` |

Do **not** treat `withdrawable_balance` as equal to `recharge_balance` when threshold > 0.

### `POST /wallet/withdraw/`

Creates a **pending** withdraw and **immediately reduces** `recharge_balance` / `balance` (reservation). Ledger `method` is always `manual`. Commission is never withdrawn.

```json
{ "amount": "200.00" }
```

**Validation (backend authoritative):**

- `amount <= withdrawable_balance` from current wallet GET
- Example: recharge `420`, meal_stop `100` → max `320`. Amount `400` → `400` with detail mentioning maximum and meal-stop reserve.

**Mobile / customer web UX:**

1. Show Available / recharge balance and **Maximum withdrawable** (`withdrawable_balance`).
2. Cap the input max to `withdrawable_balance`.
3. On over-limit: e.g. “You can withdraw maximum ৳320. Please keep ৳100 balance for meal service.”
4. Always re-validate from latest `GET /wallet/` before submit.

### History

- `GET /wallet/transactions/`
- `GET /wallet/transactions/{public_id}/`

Customer fields may include `reviewed_at`, `rejection_reason`, `transaction_id` (recharge). **No** reviewer identity/email.

## Admin endpoints

Base: `/api/v1/web/wallet-funding/`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/requests/?type=&status=&q=&page=` | Filter `type=recharge\|withdraw`, `status=pending\|completed\|failed`, optional people search `q` (name/email/username/phone/customer UUID) |
| GET | `/requests/{public_id}/` | Full audit including reviewer; for withdraw show balance before / amount / remaining + meal-stop |
| POST | `/requests/{public_id}/approve/` | Empty body; withdraw approve debits Admin Wallet `customer_withdraw` |
| POST | `/requests/{public_id}/reject/` | `{ "reason": "optional" }` |

### Admin withdraw approve UI (funding panel)

When reviewing a **pending withdraw**, show:

| Label | Source |
|-------|--------|
| Customer balance before | Wallet total / recharge at request time (or current remaining + amount) |
| Withdraw amount | Request `amount` |
| Remaining after approve | Projected recharge/total after reservation (already applied at submit) |
| Meal stop threshold | `GET .../order-wallet-settings/` or wallet `meal_stop_threshold` |

New requests are already capped at meal-stop-aware maximum. Do **not** expect Admin Wallet `total_customer_funding` to decrease on approve — platform cash falls via `customer_withdraw`; use `net_customer_funding` for remaining custody liability.

Kill switch does **not** block these admin routes.

Status mapping for UI: `completed` ≈ approved, `failed` ≈ rejected.

## Error codes

| HTTP | When |
|------|------|
| 400 | Invalid amount/decimals/method/blank trx id; exceeds meal-stop-aware maximum; frozen (new submits) |
| 401 | Missing/invalid auth |
| 403 | Not verified customer/admin; customer create while `WALLET_MANUAL_FUNDING_ENABLED=false` |
| 404 | Unknown / foreign public_id |
| 409 | Duplicate **live** provider trx id (`pending`/`completed` only); idempotency conflict; already processed approve/reject; Admin Wallet float shortfall on withdraw approve |

## UX notes

- Payment destination numbers/instructions are **frontend-owned** for this release.
- After recharge submit, show “pending verification”, not “balance updated”.
- After withdraw submit, balance drop is expected (held funds).
- Idempotent retries may return `completed`/`failed` if admin already acted — use returned `status`, do not assume still pending.

## Post-approve customer notifications (no admin UI change)

`POST .../approve/` on a **pending recharge** is unchanged for the admin panel. After a successful approve the backend automatically:

1. Sends the customer an FCM push (`type=wallet_recharge_approved`)
2. Emails a branded wallet recharge invoice

Admin UI should **not** show a separate “send invoice” control for this release. Failures of push/email do not change the approve API success response. See `wallet/docs/backend/wallet-recharge-approval-notifications.md` and the mobile FCM section in that doc.

## Meal service restore on recharge approve

Backend-owned. After a successful pending **recharge** approve, if the customer was meal-stop blocked and post-credit spendable balance (`Wallet.balance`) is `>=` the live `meal_stop_threshold`, the backend clears:

- `meal_service_blocked_low_balance` → `false`
- `meal_service_blocked_at` → `null`

Approve `200` includes additive:

```json
{
  "meal_service_restored": true
}
```

| Value | Meaning |
|-------|---------|
| `true` | This approve cleared low-balance meal-stop |
| `false` | Not blocked, still below threshold, withdraw approve, list/detail/reject, etc. |

**Admin UI (optional):** if `meal_service_restored === true`, show toast “Meal service restored”. Do **not** compute thresholds on the frontend.

**Customer apps:** no change. There is **no** dedicated “meal service restored” push/email; only the existing recharge-approved notifications.

**No migration** — uses existing customer profile fields.
