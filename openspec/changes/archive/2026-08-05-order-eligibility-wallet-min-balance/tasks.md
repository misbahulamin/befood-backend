## 1. Audit month-package lock

- [x] 1.1 Review `check_existing_monthly_lock` / `MONTH_LOCK_STATUSES` vs live order create API and confirm cancelled orders do not lock
- [x] 1.2 Confirm existing API tests cover second-order reject and cancelled replacement; add any missing service-level unit cases from `order-month-package-lock` spec
- [x] 1.3 Fix gaps only if audit finds incorrect statuses, messaging, or bypass paths (otherwise document as verified)

## 2. Order wallet settings model & admin API

- [x] 2.1 Add `OrderWalletSettings` singleton (`min_wallet_balance_to_order` default `500.00`, `>= 0`, two decimal places) with `load()` / `pk=1` pattern
- [x] 2.2 Migration + Django admin registration
- [x] 2.3 Admin serializer + `GET|PATCH` view (`IsVerifiedAdmin`) mounted under orders URLs (e.g. `order-wallet-settings/`)
- [x] 2.4 OpenAPI examples for get/update and validation errors (negative / too many decimals)

## 3. Wallet minimum gate on order create

- [x] 3.1 Implement `check_wallet_min_balance(customer)` (missing wallet → 0; frozen → reject; compare `balance >=` settings minimum) and domain error type(s)
- [x] 3.2 Call gate in `create_meal_order` after month lock; map errors in `OrderCreateSerializer` like `MonthLockError`
- [x] 3.3 Ensure no wallet debit / no `payment` ledger row on successful order create

## 4. Customer visibility of minimum

- [x] 4.1 Expose read-only `min_wallet_balance_to_order` on customer wallet GET (or agreed customer-safe read path)
- [x] 4.2 Update wallet serializer/OpenAPI accordingly

## 5. Tests

- [x] 5.1 Admin settings: defaults, patch to 600/300, non-admin 401/403, negative rejected
- [x] 5.2 Order create: balance ≥ min succeeds without balance change; below min / missing wallet / frozen rejected
- [x] 5.3 Month lock still wins when both month lock and low balance apply
- [x] 5.4 Update existing order-create test fixtures that would fail under default min 500 (credit wallet or set settings in setUp)

## 6. Documentation

- [x] 6.1 Backend docs: eligibility order (month lock → wallet min), settings model, no-debit note
- [x] 6.2 Frontend docs: admin settings UX; customer order errors; wallet field for minimum; example payloads
