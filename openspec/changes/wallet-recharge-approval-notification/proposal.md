## Why

When a customer submits a wallet recharge, admins already receive an email — but after admin approval the customer gets no confirmation. Customers need a clear success signal (mobile push with amount and updated balance) plus a professional invoice email they can keep as a receipt. Without this, approved recharges feel incomplete and support load increases.

## What Changes

- After a verified admin successfully approves a pending customer recharge, the system automatically sends a customer mobile push notification (amount, updated balance, date/time).
- After the same successful approval, the system generates a unique invoice identity and emails a professional branded HTML invoice to the customer (with plain-text alternative).
- Invoice email reuses existing Befood email branding (logo, colors, contact, social links) and uses a reusable invoice template structure extensible to future transaction types.
- Notifications are scheduled only on the real `pending → completed` transition, post-commit, best-effort (SMTP/FCM failure must not roll back approval or wallet credit).
- Existing pending-submit admin email and approve/reject balance/custody behavior remain unchanged (no breaking API contract).
- Backend docs (and light mobile/admin client notes) document the post-approval notification contract and FCM data payload.

## Capabilities

### New Capabilities
- `wallet-recharge-approval-customer-notifications`: Post-approval customer FCM push + orchestration hooks (idempotent, best-effort, does not alter approval outcome).
- `wallet-recharge-invoice-email`: Professional branded recharge invoice email content, fields, and delivery rules.
- `transaction-invoice`: Reusable invoice identity (unique invoice number) and branded email template foundation for transaction receipts, starting with wallet recharge and designed for future extension.

### Modified Capabilities
- `wallet-funding`: Clarify that admin-approved pending recharges (completed credits) MUST schedule customer post-approval notifications without changing credit/custody semantics.

## Impact

- **Backend:** `wallet/services/funding.py` (`approve_recharge` post-commit hook); new notification/invoice services under `wallet/services/` and/or `notifications/services/`; optional invoice number persistence on `WalletTransaction` or a small invoice model; email templates under `templates/emails/` extending `base_branded_email.html`; reuse `email_branding.build_brand_email_context`, `get_user_device_tokens`, `send_to_tokens`.
- **Admin frontend:** No required UI change for approve; docs note that approve triggers push + invoice email automatically.
- **Mobile app:** Handle FCM payload for recharge approval (display notification; optional deep-link to wallet).
- **Dependencies:** Existing Django email stack, Firebase Admin FCM path, branded email static/S3 assets (`EMAIL_LOGO_URL`, social icon URLs).
- **Out of scope:** Reject notifications; admin invoice PDF download UI; live payment-gateway invoices; inventory purchase invoices.
