# Wallet recharge approval — customer push & invoice email

After an admin **approves** a pending customer recharge, the backend credits the wallet (existing behavior) and then, **after commit**, sends:

1. Mobile FCM push to the customer’s registered devices
2. A branded professional invoice email (HTML + plain text)

Admin pending-submit emails and approve/reject credit/custody rules are unchanged.

## Flow

```text
POST /api/v1/web/wallet-funding/requests/{public_id}/approve/
  → approve_recharge (atomic)
       credit customer wallet
       status → completed
       assign invoice_number + previous_balance snapshot
       sync Admin Wallet custody
  → transaction.on_commit
       notify_customer_recharge_approved(txn_id)
         → FCM push (best-effort)
         → invoice email (best-effort)
```

HTTP approve success does **not** depend on SMTP or FCM.

## Invoice identity

| Field | Notes |
|-------|--------|
| `WalletTransaction.invoice_number` | Unique, nullable until approve. Format `INV-WR-{YYYYMMDD}-{12 hex from public_id}` |
| `metadata.previous_balance` | Snapshot of balance before credit (`"500.00"`) |
| `metadata.customer_approval_notice_scheduled` | Set `true` when notice is scheduled at approve |

`wallet/services/transaction_invoice.py` builds a reusable context (`invoice_number`, customer fields, amounts, status, payment method/ref) for templates. First concrete type: `wallet_recharge`.

## Push contract (FCM)

| Key | Example |
|-----|---------|
| `type` | `wallet_recharge_approved` |
| `screen` | `wallet` |
| `entity_type` | `wallet_transaction` |
| `entity_id` | transaction `public_id` |
| `amount` | `"1000.00"` |
| `balance` | `"1500.00"` (updated) |
| `invoice_number` | `"INV-WR-…"` |
| `approved_at` | ISO local timestamp |

Title: `Wallet recharge approved`  
Body example: `Your wallet recharge of ৳1000.00 has been approved successfully. Your updated balance is ৳1500.00.`

Currency uses **৳** (same as wallet low-balance / meal-stop emails).

No device tokens → push skipped (logged). FCM errors → logged; approval kept.

## Invoice email

Templates:

- `templates/emails/wallet_recharge_invoice_subject.txt`
- `templates/emails/wallet_recharge_invoice_email.txt`
- `templates/emails/wallet_recharge_invoice_email.html`
- Shared table: `templates/emails/_invoice_details.html`

Uses `build_brand_email_context` (logo, contact, social links from `EMAIL_*` settings).

Content includes: invoice number, customer name/email/phone, date, payment method, provider transaction id (`external_ref`), amount, previous/updated balance, status Approved/Completed.

No usable email → skip email (logged). SMTP errors → logged; approval kept.

## Idempotency

- Notifications schedule only on real `pending → completed` inside `approve_recharge`.
- Second approve → `FundingRequestConflictError` / HTTP `409`; no second push or invoice.
- `ensure_invoice_for_recharge` keeps the same `invoice_number` on retries.

## Code map

| Module | Role |
|--------|------|
| `wallet/services/funding.py` | `approve_recharge` + `_schedule_customer_recharge_approved_notification` |
| `wallet/services/funding_customer_notifications.py` | Push + email orchestration |
| `wallet/services/transaction_invoice.py` | Invoice number + context |
| `wallet/services/funding_notifications.py` | Admin pending emails (unchanged) |

## How to verify

```bash
python manage.py test wallet.tests.test_recharge_approval_notifications
```
