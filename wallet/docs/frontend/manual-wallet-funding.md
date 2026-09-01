# Customer Wallet Funding — Frontend Integration

Manual off-platform verification. Frontend shows bKash/Nagad/Bank payment instructions; backend stores the selected method + transaction id and waits for admin approval.

## Auth

- Customer: verified customer token (`Authorization: Token …` or project JWT as used elsewhere).
- Admin: verified admin / superuser (`IsVerifiedAdmin`).

Optional: `Idempotency-Key` header (or body `idempotency_key`) on create.

## Customer endpoints

Base: `/wallet/`

### `POST /wallet/recharge/`

Creates a **pending** recharge. Balance does **not** increase until admin approve.

```json
{
  "amount": "500.00",
  "payment_method": "bkash",
  "transaction_id": "TX123456",
  "note": "optional"
}
```

`payment_method`: `bkash` | `nagad` | `bank` (not `manual`).

Response includes `wallet` + `transaction` with `status: "pending"`. API field `transaction_id` maps to ledger `external_ref`.

### `POST /wallet/withdraw/`

Creates a **pending** withdraw and **immediately reduces** spendable `wallet.balance` (reservation). Ledger `method` is always `manual`.

```json
{ "amount": "200.00" }
```

### History

- `GET /wallet/transactions/`
- `GET /wallet/transactions/{public_id}/`

Customer fields may include `reviewed_at`, `rejection_reason`, `transaction_id` (recharge). **No** reviewer identity/email.

## Admin endpoints

Base: `/api/v1/web/wallet-funding/`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/requests/?type=&status=&page=` | Filter `type=recharge\|withdraw`, `status=pending\|completed\|failed` |
| GET | `/requests/{public_id}/` | Full audit including reviewer |
| POST | `/requests/{public_id}/approve/` | Empty body |
| POST | `/requests/{public_id}/reject/` | `{ "reason": "optional" }` |

Kill switch does **not** block these admin routes.

Status mapping for UI: `completed` ≈ approved, `failed` ≈ rejected.

## Error codes

| HTTP | When |
|------|------|
| 400 | Invalid amount/decimals/method/blank trx id; insufficient balance; frozen (new submits) |
| 401 | Missing/invalid auth |
| 403 | Not verified customer/admin; customer create while `WALLET_MANUAL_FUNDING_ENABLED=false` |
| 404 | Unknown / foreign public_id |
| 409 | Duplicate provider trx id; idempotency conflict; already processed approve/reject; Admin Wallet float shortfall on withdraw approve |

## UX notes

- Payment destination numbers/instructions are **frontend-owned** for this release.
- After recharge submit, show “pending verification”, not “balance updated”.
- After withdraw submit, balance drop is expected (held funds).
- Idempotent retries may return `completed`/`failed` if admin already acted — use returned `status`, do not assume still pending.
