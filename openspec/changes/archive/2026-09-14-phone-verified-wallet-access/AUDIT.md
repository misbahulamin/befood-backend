# Audit notes (apply session)

## Path: phone register → wallet recharge

1. `verify_phone_otp` → `create_phone_only_customer` sets `is_phone_verified=True`, blank email, CUSTOMER group.
2. Customer wallet views used `IsVerifiedCustomer` → `is_customer_identity_verified` (phone OR email OR social).
3. When identity fails, DRF returned `403` with order-placement copy: `Identity verification is required before placing an order.` — easy for mobile to show as “verify before recharge.”

## Grep (wallet app)

- No `is_email_verified` hard gate in wallet views/serializers/funding services.
- Tests previously seeded only `is_email_verified=True` (no phone-only API coverage).

## Gaps closed this change

- Wallet-scoped permission + message: `IsVerifiedWalletCustomer`.
- Phone-only + unverified regression API tests.
- Docs + mobile impact checklist.
