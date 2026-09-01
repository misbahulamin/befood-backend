## Why

Customer `recharge` and `withdraw` currently credit or debit the wallet immediately with `method=manual` and `status=completed`, even though no live bKash/Nagad/Bank gateway exists. Operators cannot verify real off-platform payments before balance changes, which is unsafe for production money movement. We need a manual admin verification queue so customers submit proof (method + amount + transaction id / withdraw amount) and only verified admins finalize ledger and Admin Wallet custody updates.

## What Changes

- **BREAKING**: Customer `POST /wallet/recharge/` no longer credits balance immediately. It creates a **pending** recharge request; balance and Admin Wallet custody credit apply only after admin approve.
- **BREAKING**: Customer `POST /wallet/withdraw/` no longer completes payout immediately. It creates a **pending** withdraw with balance reserved (debited from spendable balance) so the same funds cannot be spent twice; Admin Wallet custody debit and finalization occur only after admin approve. Reject releases the reserved amount.
- Customer recharge accepts `payment_method` (`bkash` | `nagad` | `bank`) and `transaction_id` (API field mapped to ledger `external_ref`); server resolves the customer from auth (never trusts client `user_id`).
- Customer withdraw stores ledger `method=manual` with empty `external_ref`; no provider transaction id is required.
- Duplicate provider transaction ids are rejected for **provider recharge methods only** (`bkash|nagad|bank`) via partial unique constraint on `(method, external_ref)` where `type=recharge`, method is a provider method, and `external_ref` is non-empty, plus service validation (`manual` recharge refs are not in this uniqueness set).
- Funding idempotency is resolved **before** duplicate-ref and balance checks: lookup by `wallet + idempotency_key` only; fingerprint (including `type`) decides replay vs `409`. Same-key same-fingerprint replay returns the existing transaction with its **current** status (`pending`/`completed`/`failed`) without re-reserving, mutating balance/custody, or re-emailing; conflicting fingerprint (including recharge vs withdraw on the same key) returns `409`.
- Add `bank` to wallet funding method choices; keep `manual` for withdraw/internal paths (not accepted as customer recharge method).
- Add review audit fields: `reviewed_by` → nullable FK to **User** (supports profile-less superusers allowed by `IsVerifiedAdmin`), `reviewed_at`, `rejection_reason`.
- Approve/reject are **side-effect idempotent / exactly-once in effect**: second attempt on non-pending returns `409`, with no duplicate balance or custody mutation.
- `WALLET_MANUAL_FUNDING_ENABLED` gates **only new** customer recharge/withdraw submissions; admins may still list/detail/approve/reject already-pending requests when the flag is off.
- Wallet freeze blocks **new** customer funding submissions; verified-admin resolution of already-pending requests remains allowed (including withdraw reject to restore reservation and recharge approve/reject).
- Admin emails fire only after successful commit of a **new** pending row (`transaction.on_commit`); failures are caught/logged; idempotent replay does not resend.
- Deterministic HTTP error contracts (`400` / `401` / `403` / `404` / `409`) across funding APIs.
- Customer vs admin serializers stay separated (customers do not see reviewer identity).
- Update tests, OpenAPI, and frontend/backend wallet docs for the new contracts.

## Capabilities

### New Capabilities

- `manual-funding-admin-review`: Verified-admin list/detail/approve/reject for customer recharge and withdraw funding requests, including status transitions, audit fields, side-effect-idempotent processing, frozen-wallet resolution rules, kill-switch independence for already-pending rows, and deterministic error contracts.
- `wallet-funding-admin-notifications`: Post-commit email notifications to verified admins (and eligible superusers) on **new** pending funding creates only; SMTP failure isolation; no resend on idempotent replay.

### Modified Capabilities

- `wallet-funding`: Change customer recharge/withdraw from immediate completed manual funding to pending manual-verification requests; idempotency-before-validation ordering; recharge-scoped duplicate provider refs; withdraw `method=manual`; shared amount max validation; kill-switch and freeze semantics for new vs existing requests.
- `admin-wallet-funding-custody`: Move Admin Wallet custody sync to **admin approval** time; insufficient-float approve is fully non-mutating (`409`, request stays pending, review fields untouched).
- `customer-wallet`: Clarify that spendable `balance` already reflects reserved pending withdraws so meal payment and order eligibility continue to use the same balance field safely; customer-visible review fields exclude admin identity.

## Impact

- **Apps**: `wallet` (models, funding services, serializers, views, urls, tests, docs), `admin_wallet` (ingestion call timing / lock-order awareness), `user_management` (reuse `IsVerifiedAdmin` / recipient lookup), `core` (web URL mount).
- **APIs**: Customer funding contracts use `transaction_id` (not dual-named fields); admin funding review under `/api/v1/web/wallet-funding/`; deterministic status codes.
- **Data**: Migration for `bank`, User-FK `reviewed_by`, review timestamps/reason, provider-method recharge-scoped partial unique constraint with historical duplicate preflight; existing completed/manual rows remain valid.
- **Dependencies**: Reuse Django email stack; no new payment gateway or mail library.
- **Ops**: Rollback to legacy instant funding MUST NOT proceed while unresolved pending withdraws exist unless reservations are resolved first.
- **Clients**: Frontend shows payment instructions locally; treats submit success as pending request, not balance update.
