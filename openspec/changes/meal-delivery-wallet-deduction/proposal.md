## Why

Customers are charged only through order eligibility (minimum wallet balance) today; wallet balance is never debited when a meal is actually delivered. BeFood needs pay-per-delivered-meal: deduct the package’s final per-meal price from the customer wallet only when delivery completes, so skipped / pending / failed slots are never charged and each delivered slot produces one clear wallet history entry.

## What Changes

- On transition of an `OrderDelivery` to `delivered`, automatically debit the customer wallet by the order’s per-meal price (the published final meal price frozen at order time: ingredient cost + per-meal operational cost + profit).
- Create a completed wallet ledger transaction (`type=payment`, `direction=debit`) with meal-payment metadata (meal/package name, service date, lunch/dinner, amount, order/delivery references).
- Do **not** debit for `scheduled`, `skipped` (customer meal-off or admin skip), or `missed` deliveries.
- Prevent duplicate charges for the same delivery slot (idempotent payment keyed to the delivery).
- Expose meal-payment details on customer wallet transaction history so the UI can show what was charged.
- Document admin and customer-facing behavior for insufficient / frozen wallet on delivery completion.

## Capabilities

### New Capabilities
- `meal-delivery-wallet-payment`: Charge the customer wallet exactly once when a delivery slot becomes `delivered`, using the order per-meal price snapshot, with eligibility guards (meal-off / skip / miss / non-delivered) and wallet history metadata.

### Modified Capabilities
- `customer-wallet`: Customer wallet transaction list/detail MUST surface meal-payment metadata (service date, meal period, package/meal name, related delivery/order identifiers) for payment debits created by meal delivery.
- `wallet-funding`: Clarify that `type=payment` debits are produced by delivery completion (not by order create or manual withdraw), without changing recharge/withdraw funding rules.

## Impact

- **orders**: `mark_delivery` (and any other path that sets `delivered`) integrates with a meal-payment service; optional payment status / wallet transaction link on `OrderDelivery`.
- **wallet**: Reuse `debit_wallet` with `type=PAYMENT`, idempotency keys, and richer transaction `metadata` / serializer fields for history.
- **meals / pricing**: Reuse existing final price already snapshotted on `Order.per_meal_price_snapshot` (from cycle costing + publish); no change to ingredient / operational-cost / profit formulas.
- **APIs**: Wallet transaction responses gain meal-payment fields; delivery mark behavior gains side effects (debit) documented for admin/ops and deliveryman flows.
- **Tests / docs**: New service + API tests; backend/frontend docs under `orders` and `wallet`.
