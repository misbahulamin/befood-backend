# Delivery Fee Deduction — Backend Notes

## What this is

Phase 1: verified admins manually deduct a monthly delivery fee from a customer wallet. Each deduct creates:

1. A completed `WalletTransaction` with `type=delivery_fee_payment`
2. A `DeliveryFeePayment` ledger row (month/year scoped, auditable)
3. Best-effort inbox + FCM notification after commit

## Models

### `DeliveryFeePayment` (`wallet.models`)

| Field | Notes |
|-------|--------|
| `public_id` | UUID client identity |
| `customer` | FK → `CustomerProfile` |
| `amount` | Decimal BDT |
| `payment_month` / `payment_year` | Billing period |
| `status` | `paid` \| `reversed` (reversal endpoint not in Phase 1) |
| `deducted_by_admin` | FK → `AdminProfile` |
| `wallet_transaction` | OneToOne → debit row |
| `reason` | Required audit text |
| `source` | `manual` (default) \| `automatic` (future) |
| `fee_rule_code`, `service_area_public_id`, `metadata` | Future automation hooks |

**Constraint:** at most one `paid` row per `(customer, payment_year, payment_month)`.

### Wallet type

`WalletTransaction.Type.DELIVERY_FEE_PAYMENT = 'delivery_fee_payment'`  
Debit strategy: `commission_first` (same as meal `payment`).

## Service flow

`wallet.services.delivery_fee.charge_delivery_fee(...)`

1. Validate amount, reason, period
2. `select_for_update` wallet
3. Idempotency replay if key matches existing fee debit
4. Reject if paid row already exists for month (`DeliveryFeeAlreadyPaidError` → API `409`)
5. `debit_wallet(..., type=DELIVERY_FEE_PAYMENT)`
6. Set `reviewed_by` / `reviewed_at` on txn
7. Create `DeliveryFeePayment`
8. `evaluate_meal_stop_after_debit(customer)`
9. `transaction.on_commit` → `notify_customer_delivery_fee_deducted`

## Custody note (Admin Wallet)

Delivery-fee debit **does not** credit or debit platform `AdminWallet` cash. Prepaid funding already sits in custody; fee deduction reallocates customer prepaid balance only. Reporting uses `DeliveryFeePayment` aggregates.

## Notifications

- Type: `delivery_fee_deducted`
- Screen: `wallet`
- Inbox always attempted; FCM best-effort
- Failures never roll back the debit

## Pending customers (monthly report)

`pending_customers` = count of customers with an **active** `CustomerSubscription` who do **not** have a `paid` `DeliveryFeePayment` for that `(year, month)`.

## Reversal design (future)

Do **not** mutate paid amount in place. Future reversal should:

1. Credit wallet (`refund` or dedicated fee-refund type)
2. Mark payment `status=reversed` (or link a reversal row)
3. Keep original debit + payment for audit

## APIs

| Path | Module |
|------|--------|
| Customer context / deduct / history | `user_management.api.admin_customer_views` |
| Global list + reports | `wallet.api.delivery_fee_views` / `wallet.api.delivery_fee_urls` |

Mounted at `/api/v1/web/delivery-fees/` and nested under `/api/v1/web/customers/{public_id}/`.

## Migration

`wallet/migrations/0006_delivery_fee_payment.py` — additive; no backfill.
