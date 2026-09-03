## 1. Analysis & data model

- [x] 1.1 Confirm approve path (`approve_recharge`), admin pending email hook, branding helpers, and FCM send helpers against current code (no behavior change yet)
- [x] 1.2 Add unique nullable `invoice_number` on `WalletTransaction` (migration) and decide metadata keys for `previous_balance` / notice flags
- [x] 1.3 Implement invoice number generator + `ensure_invoice_for_recharge(txn)` in `wallet/services/transaction_invoice.py` (idempotent; reusable context shape)

## 2. Invoice email templates

- [x] 2.1 Add reusable invoice-oriented email structure (shared blocks or dedicated base extending branded layout) under `templates/emails/`
- [x] 2.2 Add `wallet_recharge_invoice` subject / text / HTML templates with header brand, customer block, recharge details, balances, status
- [x] 2.3 Wire template context via `build_brand_email_context` + invoice extras (logo, contact, social links when configured)

## 3. Customer notification orchestration

- [x] 3.1 Implement `wallet/services/funding_customer_notifications.py`: FCM push (`type=wallet_recharge_approved`, amount, updated balance, timestamp, routable data keys)
- [x] 3.2 Implement invoice email send (HTML + text) using invoice service; isolate push vs email failures
- [x] 3.3 Schedule `notify_customer_recharge_approved` from `approve_recharge` via `transaction.on_commit` only on real `pending → completed` transition
- [x] 3.4 Persist previous balance snapshot and invoice number inside the approve transaction before commit

## 4. Tests

- [x] 4.1 Test approve credits once, assigns one invoice number, and schedules/sends customer push + invoice email (mail outbox / FCM mocked)
- [x] 4.2 Test second approve returns conflict and does not resend push or invoice
- [x] 4.3 Test SMTP failure and FCM failure leave completed recharge + custody intact; missing email / missing tokens skip gracefully
- [x] 4.4 Test invoice content fields: amount, previous/updated balance, method, external_ref, customer identity, status

## 5. Docs & clients

- [x] 5.1 Write/update `wallet/docs/backend/` note for post-approval push + invoice (flow, fields, idempotency, failure behavior)
- [x] 5.2 Add short admin frontend note (approve unchanged; triggers customer push + invoice automatically) under existing wallet-funding frontend docs
- [x] 5.3 Document mobile FCM contract (`type`, `screen`, `entity_type`, `entity_id`, amount/balance) for `befood_mobile` handlers
- [x] 5.4 Confirm currency display consistency (৳ vs TK) in push body and invoice copy with existing wallet emails
