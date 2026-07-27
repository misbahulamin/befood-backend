## 1. App foundation and models

- [x] 1.1 Flesh out `wallet` app config (`apps.py`) and ensure package imports are valid
- [x] 1.2 Implement `Wallet` model (`OneToOne` to `CustomerProfile`, `balance`, `currency`, `status`, `PublicIdMixin`, timestamps)
- [x] 1.3 Implement append-only `WalletTransaction` model (`public_id`, type, direction, amount, balance_after, status, method, external_ref, idempotency_key, note, metadata, timestamps)
- [x] 1.4 Create/fix initial migration (verify empty `0001_initial` state) and apply locally

## 2. Ledger service layer

- [x] 2.1 Implement `get_or_create_wallet(customer_profile)` and shared amount validators (positive, ≤2 dp, max cap)
- [x] 2.2 Implement atomic `credit_wallet` / `debit_wallet` with `select_for_update`, frozen-wallet checks, and `balance_after` snapshots
- [x] 2.3 Implement `recharge_wallet` and `withdraw_wallet` (manual completed path + optional idempotency key / 409 on conflict)
- [x] 2.4 Add settings flag `WALLET_MANUAL_FUNDING_ENABLED` (and respect it in funding services)
- [x] 2.5 Add reserved helpers or documented hooks for future pending→completed gateway completion (no live provider calls)

## 3. Customer API

- [x] 3.1 Add serializers for wallet summary, transaction list/detail, and recharge/withdraw request/response (UUID identity only)
- [x] 3.2 Implement views: `GET /wallet/`, `GET /wallet/transactions/`, `GET /wallet/transactions/{public_id}/`, `POST /wallet/recharge/`, `POST /wallet/withdraw/` with `IsVerifiedCustomer` and ownership scoping
- [x] 3.3 Wire `wallet.api.urls` and mount `path('wallet/', ...)` in `core/urls.py`
- [x] 3.4 Add `extend_schema` / OpenAPI annotations for all endpoints

## 4. Admin

- [x] 4.1 Register `Wallet` and `WalletTransaction` in Django admin with list/search/filter; keep balance and completed amounts read-oriented

## 5. Tests

- [x] 5.1 Replace/extend `wallet/tests/test_basic.py` for credit/debit ledger invariants and insufficient funds
- [x] 5.2 API tests: wallet get-or-create, auth `401`, ownership isolation
- [x] 5.3 API tests: successful recharge/withdraw, invalid amounts, frozen wallet, insufficient withdraw
- [x] 5.4 API tests: idempotency replay and `409` on key reuse with different amount
- [x] 5.5 API tests: transaction list/detail and foreign `public_id` → `404`

## 6. Documentation

- [x] 6.1 Add `wallet/docs/frontend/customer-wallet.md` (endpoints, auth, money format, examples, manual vs future bKash/Nagad, UUID rules)
- [x] 6.2 Add `wallet/docs/backend/customer-wallet.md` (models, ledger invariants, concurrency, gateway seam, verification steps)
