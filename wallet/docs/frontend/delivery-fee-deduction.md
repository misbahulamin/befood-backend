# Delivery Fee Deduction — Admin Frontend Integration

## Summary

Verified admins can manually deduct a **monthly delivery fee** from a customer wallet, view fee history, and read monthly/lifetime collection stats. Phase 1 is **manual only** (no auto-cron).

**Auth:** `Authorization: Token <verified-admin-token>`  
**Permission:** `IsVerifiedAdmin`  
**Money:** decimal strings, 2 places, BDT

---

## Recommended UI flow (select → amount → confirm)

1. Admin opens customer (or search) and loads context:
   - `GET /api/v1/web/customers/{public_id}/delivery-fee-context/`
2. Show: name, phone, wallet balance, active subscription, prior fee history, current-month paid amount.
3. Admin enters:
   - `amount` (e.g. `300.00`)
   - `payment_month` (1–12)
   - `payment_year` (e.g. `2026`)
   - `reason` (required, e.g. `September Delivery Fee`)
4. Confirm → `POST /api/v1/web/customers/{public_id}/delivery-fee-payments/`
5. On success (`201`): refresh balance + history; show confirmation toast.
6. Always send `Idempotency-Key: <uuid>` so double-clicks / retries do not double-charge.

---

## Endpoint grid

| Method | Path | Why |
|--------|------|-----|
| `GET` | `/api/v1/web/customers/{public_id}/delivery-fee-context/` | Prefill deduct screen |
| `GET` | `/api/v1/web/customers/{public_id}/delivery-fee-payments/` | Customer fee history (paginated) |
| `POST` | `/api/v1/web/customers/{public_id}/delivery-fee-payments/` | Deduct fee |
| `GET` | `/api/v1/web/delivery-fees/payments/` | Global payment list |
| `GET` | `/api/v1/web/delivery-fees/reports/monthly/?year=&month=` | Dashboard month cards |
| `GET` | `/api/v1/web/delivery-fees/reports/lifetime/` | Lifetime cards |

---

## POST deduct

```http
POST /api/v1/web/customers/{public_id}/delivery-fee-payments/
Authorization: Token ...
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "amount": "300.00",
  "payment_month": 9,
  "payment_year": 2026,
  "reason": "September Delivery Fee"
}
```

**Success `201`:**

```json
{
  "public_id": "...",
  "customer_public_id": "...",
  "amount": "300.00",
  "payment_month": 9,
  "payment_year": 2026,
  "period_label": "September 2026",
  "status": "paid",
  "reason": "September Delivery Fee",
  "source": "manual",
  "deducted_by_admin": "Admin Shohan",
  "wallet_transaction_public_id": "...",
  "wallet_balance_after": "950.00",
  "created_at": "...",
  "paid_at": "..."
}
```

Idempotent replay of the same key returns **`200`** with the original payment (no second debit).

---

## Error handling (UI states)

| HTTP | Meaning | UI |
|------|---------|-----|
| `400` | Insufficient wallet balance / frozen wallet / invalid amount or period | Show `detail` (e.g. `Insufficient wallet balance`) |
| `409` | Already paid for that month, or idempotency conflict | Block confirm; show already-paid state |
| `401` / `403` | Auth / not verified admin | Redirect / deny |

---

## Reports (dashboard widgets)

### Monthly

`GET /api/v1/web/delivery-fees/reports/monthly/?year=2026&month=9`

| Field | Card |
|-------|------|
| `total_collected` | Total Delivery Fee Collected |
| `customers_paid` | Total Customers Paid |
| `pending_customers` | Pending Customers (active subscribers without paid fee that month) |

### Lifetime

`GET /api/v1/web/delivery-fees/reports/lifetime/`

| Field | Card |
|-------|------|
| `total_collected` | Lifetime amount |
| `customers_paid` | Distinct paid customers |

### Global list filters

`GET /api/v1/web/delivery-fees/payments/?year=&month=&customer=&status=&q=`

Unsupported query keys → **`400`** with `error_code: UNSUPPORTED_FILTER`.

---

## Customer fee history fields

Render each row as:

- Period label (`September 2026`)
- Amount
- Status (`paid`)
- Paid date (`paid_at` / `created_at`)
- Deducted by (admin display name)

---

## Meal vs delivery-fee wallet history (mobile / customer apps)

Customer wallet transactions use **distinct types**:

| Type | Render as |
|------|-----------|
| `payment` (+ `meal_payment` block) | Meal charge |
| `delivery_fee_payment` (+ `delivery_fee` block) | Delivery fee deduction |

Do **not** treat `delivery_fee_payment` rows as meals. See `wallet/docs/frontend/customer-wallet.md`.

---

## Related docs

- Backend: `wallet/docs/backend/delivery-fee-deduction.md`
- Customer 360: `user_management/docs/frontend/admin-customer-management.md`
