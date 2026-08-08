## 1. App scaffold and models

- [x] 1.1 Create `admin_wallet` Django app package (`models`, `services`, `api`, `admin`, `management`, `tests`, `docs`) and register it in `INSTALLED_APPS`
- [x] 1.2 Implement `AdminWallet` singleton model (`public_id`, `balance`, `currency`, `status`, optional lifetime counters) with seed helper
- [x] 1.3 Implement append-only `AdminWalletTransaction` model with type/direction/status/method enums, source/reference fields, optional order/delivery/customer/admin/customer-txn links, `idempotency_key` unique per wallet, indexes
- [x] 1.4 Implement `AdminWalletAuditLog` model (actor, action, amount, previous/new balance, reason, transaction FK, timestamps)
- [x] 1.5 Generate and apply migrations; verify singleton seed path

## 2. Ledger and operations services

- [x] 2.1 Implement `credit_admin_wallet` / `debit_admin_wallet` with `select_for_update`, atomic balance update, `balance_after`, and idempotency replay behavior
- [x] 2.2 Implement `manual_deposit`, `withdraw` (balance guard + required reason), and `post_expense` (allowlisted debit types) services with audit log writes
- [x] 2.3 Implement adjustment helper (`adjustment` credit / `manual_adjustment` debit) with restricted usage and audit
- [x] 2.4 Implement query helpers for wallet summary, period aggregates (today/month), and reconcilable balance check
- [x] 2.5 Add settings flag `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` (default true in app settings pattern)

## 3. Payment ingestion hook

- [x] 3.1 Implement `credit_from_meal_payment(delivery, customer_txn)` with idempotency key scoped to delivery and full source tracking metadata
- [x] 3.2 Hook ingestion into successful `charge_delivered_meal` / mark-delivered path (prefer same atomic block; document failure policy)
- [x] 3.3 Ensure customer wallet recharge paths do not credit Admin Wallet
- [x] 3.4 Add management command `reconcile_admin_wallet_meal_payments` for missing credits without duplicates

## 4. Web Admin APIs

- [x] 4.1 Add serializers for wallet summary, dashboard, transactions, deposit/withdraw/expense requests, and audit logs
- [x] 4.2 Implement verified-admin views: wallet summary, dashboard, transaction list/detail, deposits, withdrawals, expenses, audit logs
- [x] 4.3 Mount routes under `/api/v1/web/admin-wallet/` with `IsVerifiedAdmin` (and optional permission codenames if wired)
- [x] 4.4 Implement allowlisted filters/search (`date range`, direction, type, method, status, `q`) and reject unsupported filters with `400`
- [x] 4.5 Add OpenAPI/schema helpers for all new endpoints (operationIds, examples, error responses)

## 5. Tests

- [x] 5.1 Unit/service tests: credit/debit, overdraft rejection, idempotent replay, ledger reconciliation
- [x] 5.2 Operation tests: manual deposit, withdrawal guards, typed expenses, audit log creation
- [x] 5.3 Ingestion tests: meal-delivery charge credits Admin Wallet once; retry does not double credit; failed customer charge credits nothing; recharge does not credit
- [x] 5.4 API permission tests: verified admin allowed; customer/unauthenticated denied
- [x] 5.5 API filter/search/dashboard tests for summary fields and transaction history contracts

## 6. Documentation and verification

- [x] 6.1 Write `admin_wallet/docs/backend/admin-wallet.md` (models, ledger rules, hook, idempotency, permissions, verify steps)
- [x] 6.2 Write `admin_wallet/docs/frontend/admin-wallet.md` (endpoint grid, field meanings, dashboard cards, deposit/withdraw/expense flows, filters, call order)
- [x] 6.3 Run relevant test suite and fix failures; smoke-check Admin Wallet endpoints in OpenAPI/Swagger if available
