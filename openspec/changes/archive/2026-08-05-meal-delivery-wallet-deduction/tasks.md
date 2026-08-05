## 1. Model and feature flag

- [x] 1.1 Add `OrderDelivery` payment fields (`payment_status`, FK/link to `WalletTransaction`) with migration and defaults (`not_applicable` until charged)
- [x] 1.2 Add settings flag `MEAL_DELIVERY_WALLET_CHARGE_ENABLED` (default `True`) for safe rollback of the charge hook
- [x] 1.3 Register new delivery payment fields in Django admin (read-oriented)

## 2. Meal payment service

- [x] 2.1 Implement `orders.services.meal_payment.charge_delivered_meal(delivery)` using `Order.per_meal_price_snapshot`, `get_or_create_wallet`, and `debit_wallet` with `type=payment`
- [x] 2.2 Set idempotency key `meal-delivery:{delivery.public_id}` and metadata (`purpose`, order/delivery public ids, `service_date`, `meal_period`, meal/package name)
- [x] 2.3 Guard: no-op / skip when status is not newly becoming `delivered`, when already `charged`, or when feature flag is off
- [x] 2.4 Map `InsufficientFundsError` / `WalletFrozenError` to a domain error used by mark-delivery (reject mark, leave non-delivered)

## 3. Delivery integration

- [x] 3.1 Integrate charge into `mark_delivery` inside the existing atomic block only on transition to `delivered`
- [x] 3.2 Confirm meal-off / admin skip / missed paths never call charge (or call is a no-op)
- [x] 3.3 Surface wallet insufficient/frozen errors on the mark-delivery API with stable error messaging/code
- [x] 3.4 Ensure any deliveryman completion path that marks `delivered` goes through the same service entry point

## 4. Wallet history API

- [x] 4.1 Extend `WalletTransactionSerializer` to expose structured `meal_payment` (or equivalent fields) for meal-delivery payment debits
- [x] 4.2 Update OpenAPI / schema helpers for wallet transaction list and detail
- [x] 4.3 Keep recharge/withdraw response shapes backward compatible when meal fields are absent

## 5. Tests

- [x] 5.1 Test mark `delivered` debits snapshot amount and creates one `payment` debit with metadata
- [x] 5.2 Test meal-off (`skipped`), admin skip, and `missed` do not debit
- [x] 5.3 Test repeated / concurrent mark `delivered` does not double-charge
- [x] 5.4 Test insufficient and frozen wallet reject mark and leave status unchanged
- [x] 5.5 Test order create still does not create a payment debit
- [x] 5.6 Test wallet transaction list/detail returns meal-payment context for charged deliveries

## 6. Documentation

- [x] 6.1 Write/update `orders/docs/backend/` and `orders/docs/frontend/` for delivery wallet charge behavior and errors
- [x] 6.2 Write/update `wallet/docs/backend/` and `wallet/docs/frontend/` for payment type + meal history fields
- [x] 6.3 Note that charge uses order `per_meal_price_snapshot` (final price at purchase), not live admin cost recalculation
