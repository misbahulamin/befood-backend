## Context

BeFood already runs a customer wallet ledger (`wallet` app) and platform custody cash (`admin_wallet`). Meal delivery charges use `debit_wallet` with `WalletTransaction.type=payment` and `metadata.purpose=meal_delivery` from `orders/services/meal_payment.py`. Admin money mutations use `IsVerifiedAdmin`. Customer funding is pending `WalletTransaction` rows reviewed under `/api/v1/web/wallet-funding/`. There is **no** wallet path for delivery fees today; zone `delivery_fee` settings exist but are not charged to wallets.

Product wants Phase 1 **manual** verified-admin deduction of a monthly delivery fee from the customer wallet, with payment history, dashboard stats, push/inbox notification, and admin audit—without breaking meal payment or Admin Wallet custody accounting.

Stakeholders: Admin Panel (ops), customers (wallet history + notification), backend wallet/orders/notifications teams.

Constraints: decimal money only; append-only ledger; idempotent retries; best-effort notifications after commit; reuse existing debit + meal-stop threshold patterns.

## Goals / Non-Goals

**Goals:**

- Persist `DeliveryFeePayment` rows (month/year scoped) linked 1:1 to completed wallet debits.
- Add wallet transaction type `delivery_fee_payment` distinct from meal `payment`.
- Verified-admin APIs: customer deduct context, deduct, list history, monthly/lifetime reporting.
- Reject insufficient balance with a clear client message; never overdraw.
- Notify customer (inbox + FCM) after successful deduct without rolling back money.
- Track actor admin, reason, amount, billing period, and timestamps for audit.
- Schema hooks for future automation (`source`, nullable schedule/area fields) without implementing auto-deduct.

**Non-Goals:**

- Automatic fee calculation by area, delivery count, customer type, or household.
- Cron / month-start auto-debit.
- Changing meal-delivery charge logic or Admin Wallet cash custody on meal/fee debits.
- Building the Admin Panel React UI in this repo (API + frontend docs only).
- Full refund UI in Phase 1 (design for append-only reversal; implement refund endpoint only if needed for audit completeness—prefer document + stub service hook).

## Decisions

### 1. Own the feature in the `wallet` app

- **Choice:** Model `DeliveryFeePayment` in `wallet`, services in `wallet/services/delivery_fee.py`, notifications in `wallet/services/delivery_fee_notifications.py`, web routes under `/api/v1/web/delivery-fees/` (and customer-nested helpers under `/api/v1/web/customers/{public_id}/...` where UX is customer-scoped).
- **Why:** Money movement is customer-wallet-centric; meal charge stays in `orders`; avoids `admin_wallet` custody confusion.
- **Alternatives:** `orders` app — couples fee to delivery lifecycle incorrectly. New Django app — unnecessary wiring for one ledger.

### 2. New wallet transaction type `delivery_fee_payment` (not metadata-only)

- **Choice:** Add `WalletTransaction.Type.DELIVERY_FEE_PAYMENT = 'delivery_fee_payment'`. Debit strategy same as `payment` (`commission_first`). Note example: `September 2026 Delivery Fee`. Metadata stores `payment_month`, `payment_year`, `actor_admin_public_id`, `delivery_fee_payment_public_id`, `reason`.
- **Why:** Product requires meal vs delivery-fee distinction as first-class types; filters/reporting stay simple; `max_length=40` already allows the value.
- **Alternatives rejected:** Reuse `payment` + `purpose=delivery_fee` only — works with less migration but weaker contract vs product naming (`DELIVERY_FEE_PAYMENT`).

### 3. Admin Wallet cash unchanged on delivery-fee debit

- **Choice:** Do **not** credit/debit `AdminWallet` when deducting delivery fees (same custody model as meal charges). Reporting comes from `DeliveryFeePayment`, not platform cash counters.
- **Why:** Customer prepaid wallet already holds custody cash from funding; fee deduction is internal allocation of prepaid balance, not new cash in.
- **Alternatives:** Credit Admin Wallet as `other_income` — double-counts against funding custody; rejected for Phase 1.

### 4. Billing period uniqueness for paid rows

- **Choice:** Unique constraint on `(customer, payment_year, payment_month)` where `status=paid`. Admin deduct for a month already paid returns `409 Conflict` (or returns existing payment when idempotency key matches).
- **Why:** Product collects once per calendar month; prevents double collection.
- **Alternatives:** Allow multiple paid rows per month — complicates “pending customers” and history UX.

### 5. Pending customers = active subscribers without paid fee for the month

- **Choice:** For monthly report `pending_customers`, count customers with an **active** `CustomerSubscription` who have no `DeliveryFeePayment` with `status=paid` for that `(year, month)`.
- **Why:** Closest operable definition without a fee-obligation table; aligns with “who should pay this month.”
- **Alternatives:** All customers ever — too broad. Delivered-in-month only — undercounts subscribers who meal-off. Explicit obligation table — deferred to automation phase.

### 6. Deduct service mirrors meal charge safety rails

- **Choice:** `@transaction.atomic` service `charge_delivery_fee(...)`:
  1. Resolve customer + `get_or_create_wallet` + `select_for_update`
  2. Validate amount, wallet active, sufficient balance
  3. Enforce month uniqueness / idempotency key
  4. `debit_wallet(..., type=DELIVERY_FEE_PAYMENT, method=MANUAL, status=COMPLETED)`
  5. Create `DeliveryFeePayment` linked to txn with `deducted_by_admin`, `reason`, `source=manual`
  6. Set `reviewed_by` / `reviewed_at` on the wallet txn (funding-style audit signal)
  7. After commit: notify customer; call `evaluate_meal_stop_after_debit(customer)` for threshold consistency
- **Why:** Reuses proven ledger primitives; meal-stop stays consistent after any debit.
- **Alternatives:** Direct balance mutate — forbidden by customer-wallet ledger rules.

### 7. API surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/web/customers/{public_id}/delivery-fee-context/` | Name, phone, wallet balances, active subscription, fee payment history summary |
| POST | `/api/v1/web/customers/{public_id}/delivery-fee-payments/` | Manual deduct (`amount`, `payment_month`, `payment_year`, `reason`) + `Idempotency-Key` |
| GET | `/api/v1/web/customers/{public_id}/delivery-fee-payments/` | Customer fee history (paginated) |
| GET | `/api/v1/web/delivery-fees/payments/` | Global list (filters: month, year, customer, status, q) |
| GET | `/api/v1/web/delivery-fees/reports/monthly/` | `year`+`month` → collected amount, paid count, pending count |
| GET | `/api/v1/web/delivery-fees/reports/lifetime/` | Lifetime collected amount + distinct paid customers |

Auth: `IsVerifiedAdmin` on all. Money amounts as decimal strings. Errors follow project problem/unified error conventions already used by wallet web APIs.

### 8. Notifications

- **Choice:** After successful deduct, `transaction.on_commit` → create inbox `Notification` + FCM via existing helpers (pattern: `wallet/services/funding_customer_notifications.py`). Type e.g. `delivery_fee_deducted`, screen `wallet`. Body includes month label, amount, and new balance. Failures logged; never raise into the debit transaction.
- **Why:** Matches meal-delivery and recharge-approved notification reliability rules.

### 9. Audit model

- **Choice:** Primary audit = `DeliveryFeePayment` fields (`deducted_by_admin`, `reason`, `amount`, `payment_month/year`, `created_at`) + wallet txn `reviewed_by`/`reviewed_at`/`metadata`. No new global `AdminActionLog` table.
- **Why:** Same pattern as funding review / Admin Wallet expense (entity-local audit); queryable for “who deducted whom.”

### 10. Future automation readiness

- **Choice:** On `DeliveryFeePayment` include now:
  - `source`: `manual` \| `automatic` (default `manual`)
  - nullable `fee_rule_code`, `service_area_id` (or FK when areas mature), `metadata` JSON
  - Keep amount admin-supplied in Phase 1
- **Why:** Avoids painful schema rewrite when cron/rules land; unused fields stay null.

### 11. Reversal / auditability

- **Choice:** Phase 1 does not ship a public refund endpoint unless tasks explicitly include it. Completed rows are immutable. Future reversal MUST credit wallet with `refund` (or dedicated `delivery_fee_refund`) and mark payment `status=reversed` (or create linked reversal row)—never edit the original debit amount.
- **Why:** Satisfies “auditable/reversible” design without expanding Phase 1 scope; document the intended reversal contract in backend docs.

## Risks / Trade-offs

- **[Risk] Pending count wrong if non-subscribers should also pay** → Mitigation: document definition; revisit when fee obligation table exists.
- **[Risk] Double deduct under concurrent admin clicks** → Mitigation: unique month constraint + `Idempotency-Key` + `select_for_update`.
- **[Risk] Clients treat all `payment` types as meals** → Mitigation: new type + serializer `delivery_fee` block; keep meal serializer gated on meal purpose only.
- **[Risk] Notification failure looks like deduct failure** → Mitigation: `on_commit` best-effort; API still `201`.
- **[Risk] Low balance after fee stops meals unexpectedly** → Mitigation: reuse `evaluate_meal_stop_after_debit` (desired consistency).
- **[Trade-off] One paid fee per month** → Correct for product now; multi-fee months need schema change later.

## Migration Plan

1. Add `WalletTransaction.Type` choice `delivery_fee_payment` (`AlterField`).
2. Add `DeliveryFeePayment` model + indexes/constraints + Django admin registration.
3. Deploy code + migrate (additive; no backfill required).
4. Ship web APIs + OpenAPI + frontend docs.
5. Admin Panel integrates deduct UI against documented contracts.
6. Rollback: disable routes / feature flag if needed; do not delete ledger rows; reverse via future credit procedure if money must be returned.

## Open Questions

- Exact Bangla/English notification copy ownership (product vs engineering)—default to requirement sample until product overrides.
- Should `payment_month`/`payment_year` default to “current Dhaka calendar month” when omitted?—**Recommend required fields** for explicit admin intent.
- Maximum fee amount cap (reuse wallet `validate_amount` max vs tighter business max)—**Recommend reuse ledger max unless product sets a lower cap.**
- Whether Phase 1 needs an admin refund endpoint—**default no**; document reversal design only.
