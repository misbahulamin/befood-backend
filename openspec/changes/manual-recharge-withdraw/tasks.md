## 1. Schema and model updates

- [x] 1.1 Extend `WalletTransaction.Method` with `bank`; add `reviewed_by` as nullable FK to **User** (not AdminProfile), plus `reviewed_at` and `rejection_reason`
- [x] 1.2 Add partial unique constraint scoped to **provider-method recharge** rows (`type=recharge`, `method IN (bkash,nagad,bank)`, non-empty `external_ref`) on `(method, external_ref)`; do not uniquify all transaction types or `manual` recharge refs globally by that pair
- [x] 1.3 Add migration preflight/check for historical duplicate non-empty provider-method recharge refs; define safe ops handling before applying the constraint; keep existing completed/manual rows valid when non-conflicting
- [x] 1.4 Add/review indexes useful for admin funding filters (`type`, `status`, `-created_at`)
- [x] 1.5 Create and verify a reversible Django migration; add a representative test that historical completed/manual rows survive migration assumptions

## 2. Customer funding service layer

- [x] 2.1 Implement `request_recharge`: pending credit without balance change; accept only `bkash|nagad|bank`; map sanitized API `transaction_id` -> `external_ref`
- [x] 2.2 Implement `request_withdraw`: pending debit with immediate spendable-balance reservation; persist `method=manual` and empty `external_ref`; apply shared amount max validation plus balance check
- [x] 2.3 Resolve idempotency **before** duplicate-ref and balance checks: lookup by `wallet + idempotency_key` only (no type in lookup namespace); fingerprint includes `type`/amount/(recharge method+ref); same fingerprint returns existing txn with **current** status; conflicting fingerprint (incl. recharge vs withdraw same key) -> `409`; exclude `note`
- [x] 2.4 Add DB-safe concurrent idempotency handling (per-wallet unique key + integrity/lock path) so same-key concurrent creates apply once
- [x] 2.5 Enforce recharge-scoped duplicate provider-ref validation in service + map integrity errors to `409`
- [x] 2.6 Gate only **new** customer create paths with `WALLET_MANUAL_FUNDING_ENABLED`; freeze blocks only new customer submissions
- [x] 2.7 Implement funding-specific `approve_recharge` / `reject_recharge` / `approve_withdraw` / `reject_withdraw` (not externalize `complete_pending_credit` as the business approve API)
- [x] 2.8 Approve/reject: `transaction.atomic` + documented lock order (funding txn -> customer wallet -> Admin Wallet via existing sync helpers); second transition on non-pending -> conflict/`409` with no duplicate side effects
- [x] 2.9 Withdraw float shortfall: fully non-mutating leave-pending path (`409`, reservation intact, review fields untouched)
- [x] 2.10 Frozen wallet after pending create: admin approve/reject remain allowed (including withdraw reservation release)
- [x] 2.11 Ensure customer APIs never call legacy immediate-complete `recharge_wallet` / `withdraw_wallet`

## 3. Customer APIs

- [x] 3.1 Update recharge serializer/view for `payment_method`, `amount`, `transaction_id` (+ optional note/idempotency); resolve customer from auth only; map `transaction_id` <-> `external_ref`
- [x] 3.2 Update withdraw serializer/view for pending reservation response; document/store `method=manual`; no provider transaction id required
- [x] 3.3 Keep customer history/detail serializers free of reviewer identity; allow `reviewed_at` / `rejection_reason` where useful
- [x] 3.4 Standardize HTTP responses: validation/insufficient balance -> `400`; auth -> `401`; forbidden/kill switch -> `403`; not found -> `404`; duplicate ref / idempotency conflict / already processed / float shortfall -> `409`
- [x] 3.5 Update OpenAPI examples and error mappings for the deterministic contracts above

## 4. Admin review APIs

- [x] 4.1 Add `wallet` web URL module mounted at `api/v1/web/wallet-funding/` with `IsVerifiedAdmin` (includes profile-less superusers)
- [x] 4.2 Implement paginated list + detail with filters `type` and `status`; admin serializers may expose full reviewer audit fields and funding `transaction_id`
- [x] 4.3 Implement approve/reject action endpoints calling funding-specific services; kill switch must not block these paths
- [x] 4.4 Wire OpenAPI for `409` already-processed and float-shortfall cases with stable wording

## 5. Admin email notifications

- [x] 5.1 Add helper to resolve verified admin + eligible superuser recipient emails
- [x] 5.2 Schedule branded recharge/withdraw pending emails only after successful commit of a **new** pending row via `transaction.on_commit`
- [x] 5.3 Catch/log exceptions inside the on-commit callback so SMTP errors never fail the HTTP create
- [x] 5.4 Do not schedule/send email on idempotent replay of an existing funding request

## 6. Docs

- [x] 6.1 Update backend wallet docs: pending/approve/reject flows; status mapping; withdraw `method=manual`; `transaction_id`<->`external_ref`; kill switch; freeze resolution; lock order; rollback warning for unresolved pending withdraws
- [x] 6.2 Update/add frontend wallet docs: request/response contracts, enums, admin endpoints, error code table, client-side payment instructions note

## 7. Tests

- [x] 7.1 Recharge: pending create; invalid amount/method; blank transaction id; duplicate provider ref; approve credits once; reject does not credit; non-admin cannot approve
- [x] 7.2 Withdraw: reservation create; insufficient balance `400`; above configured maximum `400`; approve finalizes custody once; reject releases reservation; non-admin cannot approve
- [x] 7.3 Idempotency: same recharge key+payload returns original; same withdraw key+payload after reservation returns original (not insufficient funds); same key across recharge vs withdraw -> `409`; conflicting payload `409`; concurrent same-key applies once; after admin approve/reject, same-key same-fingerprint replay returns same `public_id` with current `completed`/`failed` status and no new row/email/balance change
- [x] 7.4 Concurrent duplicate recharge transaction-id submissions persist only one row
- [x] 7.5 Kill switch: create while enabled, disable flag, admin can still approve/reject pre-existing pending request; customer create blocked while disabled
- [x] 7.6 Wallet frozen after pending create: admin can still reject withdraw (restore) and resolve recharge per policy
- [x] 7.7 Second approve/reject returns `409` with no duplicate balance/custody/reservation side effects
- [x] 7.8 Insufficient Admin Wallet float leaves request pending and all review fields untouched
- [x] 7.9 Notifications with `captureOnCommitCallbacks(execute=True)` (or TransactionTestCase): email after create; email failure leaves recharge pending; email failure leaves withdraw pending+reservation; idempotent replay does not resend
- [x] 7.10 AuthZ: unauthenticated `401`; non-admin `403`; superuser without AdminProfile can approve and is stored on `reviewed_by`
- [x] 7.11 Customer ownership/history omits reviewer identity; foreign public_id -> `404`
- [x] 7.12 Update legacy wallet/admin_wallet tests that asserted immediate completed manual funding
- [x] 7.13 Representative historical completed/manual rows remain valid under migration/constraint assumptions

## 8. Verification

- [x] 8.1 Run targeted wallet and admin_wallet test suites and fix regressions
- [x] 8.2 Smoke-check OpenAPI generation for new/changed endpoints
- [x] 8.3 Confirm `WALLET_MANUAL_FUNDING_ENABLED` gates only customer creates, not admin resolution
