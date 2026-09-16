## Why

Delivery fees are still collected manually outside the wallet, so admins lack an auditable, reversible ledger and customers lack clear wallet history for monthly fee charges. Phase 1 adds verified-admin manual wallet deduction with payment records, reporting, notifications, and a schema ready for later automation—without changing existing meal-payment wallet behavior.

## What Changes

- Add a dedicated `DeliveryFeePayment` ledger for monthly delivery-fee collections (customer, amount, billing month/year, status, actor admin, linked wallet transaction).
- Add a distinct customer wallet transaction type `delivery_fee_payment` (debit), separate from meal `payment` / meal-delivery purpose.
- Add verified-admin web APIs to look up customer wallet/subscription/fee history context, deduct a delivery fee with balance validation, and list fee payments.
- Add admin reporting endpoints for monthly and lifetime delivery-fee collection stats (collected amount, paid customers, pending customers).
- Send customer inbox + push notification after a successful deduction (best-effort; never roll back the debit).
- Persist admin audit fields on every deduction (who, whom, amount, month, reason, time).
- Document admin frontend contracts for the deduction UI, customer history, and dashboard widgets.
- Design schema hooks for future automation (area/household/rules) without implementing auto-deduction in this phase.

## Capabilities

### New Capabilities

- `delivery-fee-payment-ledger`: Persist delivery-fee payment records, link to wallet transactions, support month/year uniqueness rules, and keep deductions auditable/reversible via append-only ledger patterns.
- `admin-delivery-fee-deduction-api`: Verified-admin customer context + manual deduct/list APIs with insufficient-balance rejection, idempotency, and actor tracking.
- `admin-delivery-fee-reporting`: Monthly and lifetime delivery-fee collection statistics for the admin dashboard.
- `delivery-fee-notifications`: Customer inbox + FCM notification after successful delivery-fee deduction.
- `delivery-fee-frontend-docs`: Frontend-facing docs for admin selection UI, deduct confirm flow, history, and report widgets.

### Modified Capabilities

- `customer-wallet`: Customer wallet transaction list/detail MUST distinguish delivery-fee debits from meal-delivery payments and expose delivery-fee context (billing period, amount, processed-by admin signal).

## Impact

- **Apps:** `wallet` (primary model/service/API), `notifications` (inbox + FCM), `user_management` (admin customer context reuse), `orders` (active subscription readout only; no meal charge changes).
- **APIs:** New `/api/v1/web/...` delivery-fee endpoints; customer wallet serializers gain delivery-fee fields; OpenAPI updates required.
- **Ledger:** Reuse `debit_wallet` with new type; Admin Wallet cash custody unchanged (same pattern as meal charges).
- **Auth:** `IsVerifiedAdmin` for all admin money mutations.
- **Risk:** Must not break meal payment, funding approve/reject, or wallet balance invariants; post-debit meal-stop threshold evaluation should remain consistent.
- **Out of scope (phase 1):** Automatic fee calculation by area/delivery count/customer type, auto-deduction cron, household fee sharing.
