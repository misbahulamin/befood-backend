## Context

Customer wallet funding is a pending → admin-approve flow (`wallet/services/funding.py`). Submit creates a `pending` recharge and emails admins via `_schedule_funding_notification` + `funding_notifications.py`. Approval in `approve_recharge` credits the customer wallet, marks the txn `completed`, and syncs Admin Wallet custody — but does **not** notify the customer.

Existing infrastructure to reuse:

- **Email branding:** `user_management/services/email_branding.py` (`build_brand_email_context`), `templates/emails/base_branded_email.html`, logo/social URLs from `EMAIL_*` settings.
- **Customer push:** `notifications/services/device_service.get_user_device_tokens` + `fcm_service.send_to_tokens` (same pattern as `wallet_threshold_notifications.py` and meal-delivery notifications).
- **Post-commit best-effort:** `transaction.on_commit` with try/except logging (admin funding emails already do this).

Stakeholders: customers (confirmation + receipt), ops/admins (unchanged approve UX), mobile app (FCM display/routing).

## Goals / Non-Goals

**Goals:**

- On successful recharge approve only: update wallet (existing) → send customer FCM push → generate invoice identity → send branded invoice email.
- Keep approve HTTP success independent of SMTP/FCM outcomes.
- Prevent duplicate customer notifications on re-approve / concurrent approve (already `409` for non-pending).
- Provide a reusable invoice template/context structure for future transaction receipts.
- Preserve existing admin pending-submit emails and approve/reject balance + custody behavior.

**Non-Goals:**

- Customer email/push on reject or withdraw approve/reject.
- PDF attachment or admin UI to download invoices.
- Changes to inventory purchase invoice uploads.
- New mail provider or Celery requirement (in-process post-commit is enough, matching funding admin emails).
- Admin frontend approve UX redesign (docs-only if needed).
- Guaranteed delivery / retry queue beyond best-effort logging (future enhancement).

## Decisions

### 1. Hook point: `approve_recharge` service (not ViewSet only)

**Choice:** After successful balance credit + custody sync inside `approve_recharge`, schedule customer notifications with `transaction.on_commit`, mirroring `_schedule_funding_notification`.

**Why:** Any caller of `approve_recharge` (API, tests, scripts) gets the same behavior. ViewSet-only hooks can miss alternate entry points.

**Alternatives considered:** ViewSet-only post-approve calls — rejected as fragile. Signal on `WalletTransaction` save — rejected as too broad (many status writes).

### 2. Single orchestrator service

**Choice:** Add `wallet/services/funding_customer_notifications.py` with something like `notify_customer_recharge_approved(txn_id)` that:

1. Loads completed recharge txn + customer user + wallet.
2. Sends FCM push (best-effort).
3. Ensures invoice identity + builds invoice context.
4. Sends branded invoice email (best-effort).

Push and email failures are caught independently so one failure does not skip the other when practical; overall method never raises into `on_commit` callers beyond logging.

**Why:** Matches `wallet_threshold_notifications` cohesion; keeps `funding.py` thin.

### 3. Invoice identity storage

**Choice:** Persist a unique human-readable `invoice_number` on the wallet transaction (preferred: dedicated nullable unique `CharField`, or equivalently a reserved `metadata` key written once under lock). Format example: `INV-WR-{YYYYMMDD}-{short_public_id}` or sequential `INV-WR-00001234` if a counter is preferred — pick one stable scheme at implementation and document it.

Also store snapshot fields needed for the receipt when useful (e.g. `previous_balance` in metadata at approve time = `balance_after - amount`) so later emails remain accurate if wallet changes again.

**Why:** Reusable receipt identity without inventing a full invoicing domain yet; unique constraint prevents duplicates.

**Alternatives considered:** Separate `TransactionInvoice` model now — deferred; overkill for one product type. Purely derived number with no persistence — weaker for audit and future multi-type invoices.

### 4. Reusable invoice email structure

**Choice:**

- Shared partials / base blocks for invoice layout (header brand already in `base_branded_email.html`; invoice-specific table body as a dedicated template or `{% block %}` extension).
- Context builder in a small `wallet/services/transaction_invoice.py` (or `notifications/services/`) that returns a typed context: invoice number, customer info, line items / amounts, status, dates — keyed so future types can reuse the same template with different `invoice_type` / line items.
- First concrete templates: `wallet_recharge_invoice_email.html` / `.txt` / `_subject.txt`.

**Why:** Meets “professional invoice” + “extensible later” without a second branding system.

### 5. Push payload contract

**Choice:** Title/body in clear English (BDT amounts as `TK` or `৳` consistent with existing wallet threshold copy). FCM `data` allowlist-compatible keys, e.g.:

- `type`: `wallet_recharge_approved`
- `screen`: wallet screen key used by mobile (document exact value with mobile team convention)
- `entity_type`: `wallet_transaction`
- `entity_id`: txn `public_id` (string)
- Optional: `amount`, `balance`, `invoice_number` as strings

**Why:** Aligns with admin-push platform allowlisted routing keys; mobile can deep-link without parsing title text.

### 6. Idempotency / duplicate prevention

**Choice:**

- Schedule notifications **only** when `approve_recharge` actually transitions `pending → completed` (conflict path never schedules).
- Optionally set `metadata['customer_approval_notice_scheduled'] = true` (or invoice_number presence) inside the approve transaction before commit so a hypothetical double-schedule is detectable; primary guard remains status transition.
- Do **not** resend on idempotent HTTP retries that hit `409`.

**Why:** Same guarantee pattern as admin pending emails (`created=True` only).

### 7. Previous balance for invoice

**Choice:** Compute at approve time: `previous_balance = new_balance - amount` (equals wallet balance before credit). Persist in metadata for the email template.

### 8. Client impact

**Choice:** Backend-driven; admin UI unchanged. Document for admin that approve triggers customer push + invoice. Mobile docs: handle `wallet_recharge_approved` notification.

## Risks / Trade-offs

- **[Risk] SMTP/FCM down → customer never notified** → Mitigation: log with txn `public_id`; approval still succeeds; optional future resend admin action out of scope.
- **[Risk] No device token → push skipped** → Mitigation: still send invoice email; log skip (same as threshold notifications).
- **[Risk] Invoice email wider than auth emails / layout breaks in clients** → Mitigation: table-based HTML, extend proven `base_branded_email.html`, test HTML + text parts.
- **[Risk] Storing invoice on `WalletTransaction` couples receipts to wallet** → Mitigation: context builder abstracts fields; future types can add a thin invoice table without rewriting email HTML.
- **[Risk] `approve_recharge` does not call `credit_wallet` / meal-stop resume** → Mitigation: out of scope for this change; optionally note as follow-up if product wants resume-on-approve in the same on_commit.

## Migration Plan

1. Add migration for `invoice_number` (and any metadata key conventions documented in code) if a column is chosen.
2. Deploy backend; no backfill required for historical completed recharges (no retroactive emails unless a separate ops command is requested later).
3. Rollback: remove on_commit schedule / feature flag if added; historical approvals remain valid; unused invoice numbers are harmless.

Optional soft flag `WALLET_RECHARGE_CUSTOMER_NOTIFY_ENABLED` (default True) for kill-switch without code rollback — implement if project already uses similar funding flags.

## Open Questions

- Exact mobile `screen` deep-link value for wallet (confirm with `befood_mobile` routing table).
- Prefer dedicated `invoice_number` column vs metadata-only for v1 (recommendation: dedicated unique column for queryability and uniqueness).
- Currency display string: `TK` vs `৳` — align with existing customer-facing wallet threshold copy (`৳` in code today); product copy in the user request used `TK` — pick one for push + invoice and stay consistent.
